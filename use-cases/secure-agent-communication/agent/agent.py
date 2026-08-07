#!/usr/bin/env python3
"""
Secure Agent Communication — Agent Server
Uses a2a-sdk for the A2A framework. An ASGI middleware layer exposes the
gateway-compatible endpoint /a2a/tasks/send by rewriting it to / (where
the a2a-sdk registers its JSON-RPC handler) and extracts the Authorization
header into a ContextVar so the executor can forward it to the peer agent.

  GET  /.well-known/agent.json   — served by a2a-sdk
  GET  /.well-known/agent-card.json — alias served by a2a-sdk
  POST /a2a/tasks/send           — rewritten to / → a2a-sdk handler
  GET  /health                   — custom health check
"""

from uuid import uuid4
import os
import random
import re
import uuid
import logging
from contextvars import ContextVar
from datetime import datetime
from typing import Optional

import httpx
import uvicorn
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    AgentCard, AgentSkill, AgentCapabilities, AgentExtension,
    TaskStatus, TaskState, TaskStatusUpdateEvent, TextPart,
    MessageSendParams, SendMessageRequest,
)
from a2a.utils import new_agent_text_message

try:
    from a2a.types import DataPart
    _HAS_DATA_PART = True
except ImportError:
    _HAS_DATA_PART = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

IDENTITY_EXT_URI = "https://fabric.affinidi.io/extensions/agent-identity/v1"

# Carries the incoming Authorization header through the async call chain
auth_header_ctx: ContextVar[str] = ContextVar("auth_header", default="")
# Carries gateway-injected x-* headers for forwarding on outbound calls
gateway_headers_ctx: ContextVar[dict] = ContextVar(
    "gateway_headers", default={})
# Carries all request headers for logging
request_headers_ctx: ContextVar[dict] = ContextVar(
    "request_headers", default={})

# In-memory log of messages received from peer agents (not from own portal)
INCOMING_LOG: list[dict] = []

# ── Config from env ───────────────────────────────────────────────────────────
AGENT_NAME = os.environ.get("NEXT_PUBLIC_AGENT_NAME", "Agent")
AGENT_PORT = int(os.environ.get("AGENT_PORT", "8001"))
AGENT_DESCRIPTION = os.environ.get(
    "NEXT_PUBLIC_AGENT_DESCRIPTION", "A cross-org communication agent.")
PEER_AGENT_NAME = os.environ.get("NEXT_PUBLIC_PEER_AGENT_NAME", "Peer Agent")
PEER_AGENT_URL = os.environ.get("PEER_AGENT_URL", "")
PUBLIC_BASE_URL = os.environ.get(
    "NEXT_PUBLIC_AGENT_URL", f"http://localhost:{AGENT_PORT}")


def get_agent_identity(
    agent_name: str,
    role: Optional[str] = None,
    model: Optional[str] = None,
    version: str = "1.0.0",
) -> dict:
    return {
        "agentIdentity": {
            "name": agent_name,
            "model": model if model is not None else "bedrock/claude-3.5-sonnet",
            "role": role if role is not None else f"{agent_name} Server",
            "version": version,
        }
    }


# ── Mock LLM responses ────────────────────────────────────────────────────────
_RESPONSES: dict[str, list[str]] = {
    "greet": [
        "Hello! I'm {name}. How can I help you today?",
        "Hi there! {name} here — ready to assist.",
    ],
    "identity": [
        "I'm {name}, deployed to facilitate secure cross-org communication. "
        "I can chat with you or relay messages to {peer} on your behalf.",
    ],
    "capability": [
        "I can respond to your questions or relay messages to {peer}. "
        "Try: 'Send message to {peer}: Hello!'",
    ],
    "default": [
        "Understood! I'm {name}. You can also ask me to send a message to {peer}.",
        "Got it. Feel free to ask me anything, or relay a message to {peer}.",
    ],
}


def _mock_response(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["hi", "hello", "hey", "how are"]):
        key = "greet"
    elif any(w in t for w in ["who are you", "your name", "what are you"]):
        key = "identity"
    elif any(w in t for w in ["what can you", "capabilities", "help"]):
        key = "capability"
    else:
        key = "default"
    return random.choice(_RESPONSES[key]).format(name=AGENT_NAME, peer=PEER_AGENT_NAME)


# ── Intent detection ──────────────────────────────────────────────────────────
def _should_forward(text: str) -> bool:
    t = text.lower()
    peer = PEER_AGENT_NAME.lower()
    short = peer.replace(" agent", "")
    # Trigger words that imply directing a message to the peer
    verbs = ("send", "tell", "ask", "message", "ping",
             "relay", "forward", "say to", "contact")
    has_peer = peer in t or short in t
    has_verb = any(v in t for v in verbs)
    # Also match "<peer>: <text>" or message starting with peer name
    colon_pattern = bool(re.search(rf'^{re.escape(short)}[:\s]', t))
    return has_peer and (has_verb or colon_pattern)


def _extract_forward_text(text: str) -> str:
    for pat in [
        rf'(?:tell|ask|message|relay|forward|say\s+to)\s+{re.escape(PEER_AGENT_NAME.lower())}[:\-\s]+(.+)',
        rf'(?:tell|ask|message|relay|forward|say\s+to)\s+{re.escape(PEER_AGENT_NAME.lower().replace(" agent", ""))}[:\-\s]+(.+)',
        r'send\s+(?:a\s+)?(?:message\s+)?to\s+[\w\s]+?[:\-]\s*(.+)',
        r'send\s+["\'](.+?)["\'](?:\s+to)',
        rf'^{re.escape(PEER_AGENT_NAME.lower().replace(" agent", ""))}[:\s]+(.+)',
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    # Fallback: strip peer name and common verbs from the text
    cleaned = re.sub(
        rf'(?:send\s+(?:a\s+)?(?:message\s+)?to|tell|ask|message|ping|relay|forward)\s+{re.escape(PEER_AGENT_NAME.lower().replace(" agent", ""))}(?:\s+agent)?[:\-\s]*',
        '', text, flags=re.IGNORECASE
    ).strip()
    return cleaned or text


# ── Peer A2A forwarding (raw httpx → peer's /a2a/tasks/send) ─────────────────
async def _forward_to_peer(user_text: str, auth_header: str) -> dict:
    if not PEER_AGENT_URL:
        raise ValueError(f"PEER_AGENT_URL is not configured for {AGENT_NAME}")

    task_id = str(uuid.uuid4())
    message_id = uuid.uuid4().hex
    session_id = uuid.uuid4().hex
    msg_text = _extract_forward_text(user_text)

    headers = {"Content-Type": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header  # pass-through, no validation
    # Forward only x-transit-token — the gateway's proof of origin for outbound calls
    gw = gateway_headers_ctx.get()
    if transit := gw.get("x-transit-token"):
        headers["x-transit-token"] = transit

    payload = {
        "jsonrpc": "2.0",
        "id": task_id,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "kind": "message",
                "messageId": message_id,
                "contextId": session_id,
                "parts": [
                    {
                        "kind": "data",
                        "data": {
                            "action": "send:message",
                            "text": msg_text,
                        },
                    }
                ],
                "extensions": [IDENTITY_EXT_URI],
                "metadata": {IDENTITY_EXT_URI: get_agent_identity(AGENT_NAME)},
            }
        },
    }

    peer_url = PEER_AGENT_URL.rstrip("/") + "/a2a/tasks/send"
    logger.info(f"[{AGENT_NAME}] Forwarding to {PEER_AGENT_NAME} @ {peer_url}")

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        resp = await client.post(peer_url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _extract_reply_text(data: dict) -> str:
    """Extract text from either a2a-sdk response or FastAPI/plain response."""
    try:
        result = data.get("result", {})
        # a2a-sdk format: result.status.message.parts[]
        status_msg = result.get("status", {}).get("message", {})
        if status_msg:
            parts = status_msg.get("parts", [])
            texts = [p["text"] for p in parts if p.get("kind") == "text"]
            if texts:
                return "\n".join(texts)
        # Flat format: result.parts[]
        parts = result.get("parts", [])
        texts = [p["text"] for p in parts if p.get("kind") == "text"]
        if texts:
            return "\n".join(texts)
        return str(result)
    except Exception:
        return str(data)


AGENT_ID_CRED_EXT_URI = "https://fabric.affinidi.io/extensions/agent-identity-credential/v1"


def _extract_name_from_vp(metadata: dict) -> tuple[str, str]:
    """Extract agent name and raw VP from gateway VP. Returns (name, vp_raw)."""
    try:
        import json
        cred_meta = metadata.get(AGENT_ID_CRED_EXT_URI, {})
        vp_raw = cred_meta.get("verifiablePresentation", "")
        vp = json.loads(vp_raw) if isinstance(vp_raw, str) else vp_raw
        vc = vp.get("verifiableCredential", {})
        name = vc["credentialSubject"]["workloadBinding"]["agentIdentity"]["name"]
        return name, vp_raw
    except Exception:
        return "", ""


# ── a2a-sdk AgentExecutor ─────────────────────────────────────────────────────
class SecureAgentExecutor(AgentExecutor):

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message = context.message
        auth_header = auth_header_ctx.get()

        # Extract text and action from parts (handles TextPart and DataPart)
        user_text = ""
        action = ""
        for part in (message.parts or []):
            actual = part.root if hasattr(part, "root") else part
            kind = getattr(actual, "kind", None)
            if kind == "text":
                user_text = user_text or getattr(actual, "text", "")
            elif kind == "data":
                d = getattr(actual, "data", {}) or {}
                action = action or str(d.get("action", ""))
                user_text = user_text or str(d.get("text", ""))

        logger.info(f"[{AGENT_NAME}] action={action!r} text={user_text!r}")

        combined = user_text or action

        # Detect if this message came from a peer agent (not from our own portal)
        sender_identity = (message.metadata or {}).get(
            IDENTITY_EXT_URI, {}).get("agentIdentity", {})
        sender_name = sender_identity.get("name", "")
        vp_raw = ""

        # Fallback: gateway wraps outbound VP under agent-identity-credential/v1
        if not sender_name:
            sender_name, vp_raw = _extract_name_from_vp(message.metadata or {})
        is_from_peer_agent = bool(
            sender_name) and "Portal" not in sender_name and sender_name != AGENT_NAME
        # Log all incoming A2A messages — source field distinguishes portal vs peer agent
        INCOMING_LOG.append({
            "from": sender_name or "Unknown",
            "vp": vp_raw,
            "text": combined,
            "source": "agent" if is_from_peer_agent else "portal",
            "headers": request_headers_ctx.get(),
            "at": datetime.now().isoformat(),
        })
        if len(INCOMING_LOG) > 100:
            INCOMING_LOG.pop(0)

        from_peer = False

        if _should_forward(combined):
            peer_data = await _forward_to_peer(combined, auth_header)
            peer_reply = _extract_reply_text(peer_data)
            reply_text = f"[Forwarded to {PEER_AGENT_NAME}]\n\n{PEER_AGENT_NAME} says:\n{peer_reply}"
            from_peer = True
            # Log the outbound forward so Org A's agent log shows it sent to peer
            INCOMING_LOG.append({
                "from": AGENT_NAME,
                "to": PEER_AGENT_NAME,
                "text": _extract_forward_text(combined),
                "source": "forwarded",
                "headers": {},
                "vp": "",
                "at": datetime.now().isoformat(),
            })
        else:
            reply_text = _mock_response(
                combined) if combined else f"Hello from {AGENT_NAME}!"

        reply = new_agent_text_message(reply_text)
        reply.task_id = message.task_id
        reply.context_id = message.context_id
        reply.extensions = [IDENTITY_EXT_URI]
        identity = get_agent_identity(AGENT_NAME)
        identity["agentIdentity"]["fromPeer"] = from_peer
        identity["agentIdentity"]["peerName"] = PEER_AGENT_NAME if from_peer else None
        reply.metadata = {IDENTITY_EXT_URI: identity}

        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=message.task_id,
                context_id=message.context_id,
                status=TaskStatus(
                    state=TaskState.completed,
                    message=reply,
                    timestamp=datetime.now().isoformat(),
                ),
                final=True,
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("cancel not supported")


# ── Combined ASGI middleware: auth header extraction + path rewriting ─────────
class _A2AMiddleware:
    """Rewrites /a2a/tasks/send → / so a2a-sdk handler receives the request."""

    def __init__(self, app):
        self._app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            raw_headers = dict(scope.get("headers", []))
            auth = raw_headers.get(b"authorization", b"").decode(
                "utf-8", errors="ignore")
            headers_dict = {
                k.decode("utf-8", errors="ignore"): v.decode("utf-8", errors="ignore")
                for k, v in scope.get("headers", [])
                if k.lower() != b"cookie"
            }
            token = auth_header_ctx.set(auth)
            # Collect gateway-injected x-* headers for forwarding on outbound calls
            gateway_dict = {
                k: v for k, v in headers_dict.items() if k.lower().startswith("x-")}
            token2 = request_headers_ctx.set(headers_dict)
            token3 = gateway_headers_ctx.set(gateway_dict)
            if scope.get("path") == "/a2a/tasks/send":
                scope = dict(scope)
                scope["path"] = "/"
                scope["raw_path"] = b"/"
            try:
                await self._app(scope, receive, send)
            finally:
                auth_header_ctx.reset(token)
                request_headers_ctx.reset(token2)
                gateway_headers_ctx.reset(token3)
        else:
            await self._app(scope, receive, send)


# ── Build and run ─────────────────────────────────────────────────────────────
def _build_agent_card() -> AgentCard:
    return AgentCard(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        url=PUBLIC_BASE_URL.rstrip("/") + "/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(
            streaming=False,
            extensions=[
                AgentExtension(
                    uri=IDENTITY_EXT_URI,
                    description="Agent identity exchange",
                    required=False,
                    params=get_agent_identity(AGENT_NAME),
                ),
            ],
        ),
        skills=[
            AgentSkill(
                id="cross-org-chat",
                name="Cross-Org Secure Chat",
                description=(
                    f"Chat with {AGENT_NAME} directly, or relay messages "
                    f"to {PEER_AGENT_NAME} via secure A2A."
                ),
                tags=["chat", "cross-org", "a2a"],
                examples=[
                    "Hi, how are you?",
                    f"Tell {PEER_AGENT_NAME}: Hello!",
                    f"Ask {PEER_AGENT_NAME} how they are",
                    f"Ping {PEER_AGENT_NAME}",
                ],
            )
        ],
    )


def main() -> None:
    logger.info("=" * 60)
    logger.info(f"Agent : {AGENT_NAME}")
    logger.info(f"Port  : {AGENT_PORT}")
    logger.info(f"Peer  : {PEER_AGENT_NAME} @ {PEER_AGENT_URL or '(not set)'}")
    logger.info(
        f"Card  : {PUBLIC_BASE_URL.rstrip('/')}/.well-known/agent-card.json")
    logger.info("=" * 60)

    a2a_app = A2AStarletteApplication(
        agent_card=_build_agent_card(),
        http_handler=DefaultRequestHandler(
            agent_executor=SecureAgentExecutor(),
            task_store=InMemoryTaskStore(),
        ),
    ).build()

    async def health(request):
        return JSONResponse({
            "status": "healthy",
            "agent": AGENT_NAME,
            "agentCard": f"{PUBLIC_BASE_URL.rstrip('/')}/.well-known/agent-card.json",
        })

    async def incoming(request):
        return JSONResponse({"messages": INCOMING_LOG})

    async def clear_incoming(request):
        INCOMING_LOG.clear()
        return JSONResponse({"ok": True})

    a2a_app.routes.extend([
        Route("/health", health, methods=["GET"]),
        Route("/incoming", incoming, methods=["GET"]),
        Route("/incoming", clear_incoming, methods=["DELETE"]),
    ])

    uvicorn.run(
        _A2AMiddleware(a2a_app),
        host="0.0.0.0",
        port=AGENT_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
