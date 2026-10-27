#!/usr/bin/env python3
"""
Secure Agent Communication — Agent Server
Built on a2a-sdk 1.x. The wire protocol is chosen by A2A_LEGACY_MODE:

  legacy (default) — A2A 1.0 server with v0.3 compatibility enabled. Accepts
                     v0.3 `message/send` (no A2A-Version header) at / and at
                     the gateway path /a2a/tasks/send, and forwards to the
                     peer using the v0.3 data-part envelope.
  native           — strict A2A 1.0: JSON-RPC `SendMessage` at / with
                     `A2A-Version: 1.0`, ROLE_* roles, `kind`-less parts.

An ASGI middleware extracts the Authorization / x-* headers into ContextVars
so the executor can forward them to the peer agent.

  GET  /.well-known/agent-card.json — agent card
  POST /                            — A2A JSON-RPC endpoint
  POST /a2a/tasks/send              — legacy alias for / (legacy mode only)
  GET  /health                      — custom health check
"""

from uuid import uuid4
import os
import json
import random
import re
import uuid
import logging
from contextvars import ContextVar
from datetime import datetime
from typing import Optional

import httpx
import uvicorn
from google.protobuf.json_format import MessageToDict
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a.helpers.proto_helpers import new_task_from_user_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentExtension,
    AgentInterface,
    AgentSkill,
    Part,
)

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
# Mutable holder filled by the middleware with the JSON-RPC request/response bodies
exchange_ctx: ContextVar[dict] = ContextVar("exchange", default={})


def _parse_json(raw: bytes):
    try:
        return json.loads(raw)
    except Exception:
        return raw.decode("utf-8", errors="replace")[:4000] if raw else None

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
A2A_LEGACY_MODE = os.environ.get("A2A_LEGACY_MODE", "true").strip().lower() not in {
    "false", "0", "no", "off",
}
PROTOCOL_VERSION = "1.0"
LEGACY_PROTOCOL_VERSION = "0.3"
JSONRPC_BINDING = "JSONRPC"


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


# ── Peer A2A forwarding (raw httpx) ──────────────────────────────────────────
_peer_legacy_cache: dict = {}


def _card_is_legacy(card: dict) -> bool:
    """A card advertising any 1.0 interface is spoken to in 1.0; otherwise 0.3."""
    for iface in card.get("supportedInterfaces") or []:
        if str(iface.get("protocolVersion", "")).startswith("1."):
            return False
    return True


async def _peer_is_legacy(headers: dict) -> bool:
    """Discover the peer's A2A version from its agent card (cached; falls back to own mode)."""
    if "legacy" in _peer_legacy_cache:
        return _peer_legacy_cache["legacy"]
    base = PEER_AGENT_URL.rstrip("/")
    async with httpx.AsyncClient(timeout=10.0) as client:
        for path in ("/.well-known/agent-card.json", "/.well-known/agent.json"):
            try:
                resp = await client.get(base + path, headers=headers)
                if resp.status_code == 200:
                    legacy = _card_is_legacy(resp.json())
                    logger.info(f"[{AGENT_NAME}] Peer card {base + path}: "
                                f"{'v0.3' if legacy else 'v1.0'}")
                    _peer_legacy_cache["legacy"] = legacy
                    return legacy
                logger.warning(f"[{AGENT_NAME}] Peer card {base + path} -> {resp.status_code}")
            except Exception as exc:
                logger.warning(f"[{AGENT_NAME}] Peer card fetch failed {base + path}: {exc}")
    logger.warning(f"[{AGENT_NAME}] Peer card unavailable; using own mode")
    return A2A_LEGACY_MODE


def _build_peer_request(msg_text: str, legacy: bool) -> tuple[str, dict, dict]:
    """Return (url, extra_headers, JSON-RPC payload) for the peer's protocol."""
    request_id = str(uuid.uuid4())
    message_id = uuid.uuid4().hex
    identity_meta = {IDENTITY_EXT_URI: get_agent_identity(AGENT_NAME)}

    if legacy:
        # A2A v0.3 envelope (no A2A-Version header ⇒ peer treats it as 0.3)
        message = {
            "role": "user",
            "kind": "message",
            "messageId": message_id,
            "contextId": uuid.uuid4().hex,
            "parts": [{
                "kind": "data",
                "data": {"action": "send:message", "text": msg_text},
            }],
            "extensions": [IDENTITY_EXT_URI],
            "metadata": identity_meta,
        }
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "message/send",
            "params": {"message": message},
        }
        return PEER_AGENT_URL.rstrip("/") + "/a2a/tasks/send", {}, payload

    # A2A 1.0 (protobuf JSON): PascalCase method, ROLE_* enum, parts without `kind`
    message = {
        "messageId": message_id,
        "role": "ROLE_USER",
        "parts": [{"text": msg_text}],
        "extensions": [IDENTITY_EXT_URI],
        "metadata": identity_meta,
    }
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "SendMessage",
        "params": {"message": message},
    }
    headers = {"A2A-Version": PROTOCOL_VERSION, "A2A-Extensions": IDENTITY_EXT_URI}
    # Post to the configured URL exactly as given (gateway routes don't match a trailing slash)
    return PEER_AGENT_URL.rstrip("/"), headers, payload


async def _forward_to_peer(user_text: str, auth_header: str, outbound: Optional[dict] = None) -> dict:
    if not PEER_AGENT_URL:
        raise ValueError(f"PEER_AGENT_URL is not configured for {AGENT_NAME}")

    headers = {"Content-Type": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header  # pass-through, no validation
    # Forward only x-transit-token — the gateway's proof of origin for outbound calls
    gw = gateway_headers_ctx.get()
    if transit := gw.get("x-transit-token"):
        headers["x-transit-token"] = transit

    legacy = await _peer_is_legacy(
        {k: v for k, v in headers.items() if k != "Content-Type"})
    peer_url, extra_headers, payload = _build_peer_request(
        _extract_forward_text(user_text), legacy)
    headers.update(extra_headers)

    logger.info(f"[{AGENT_NAME}] Forwarding to {PEER_AGENT_NAME} @ {peer_url}")

    if outbound is not None:
        outbound["request"] = {
            "method": "POST",
            "url": peer_url,
            "headers": {
                k: ("***" if k.lower() in {"authorization", "x-transit-token"} else v)
                for k, v in headers.items()
            },
            "body": payload,
        }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(peer_url, json=payload, headers=headers)
        if outbound is not None:
            outbound["response"] = {"status": resp.status_code, "body": _parse_json(resp.content)}
        resp.raise_for_status()
        return resp.json()


def _text_from_parts(parts: list) -> str:
    # v0.3 parts carry kind:"text"; v1.0 parts are kind-less {"text": ...}
    texts = [
        p["text"] for p in parts or []
        if isinstance(p, dict) and isinstance(p.get("text"), str)
        and p.get("kind", "text") == "text"
    ]
    return "\n".join(texts)


def _extract_reply_text(data: dict) -> str:
    """Extract reply text from an A2A v0.3 or v1.0 JSON-RPC response."""
    try:
        if "error" in data:
            err = data.get("error") or {}
            return f"Peer error: {err.get('message', 'unknown error')}"
        result = data.get("result", {}) or {}
        # v1.0 wraps the payload as result.task or result.message
        task = result.get("task") or result
        message = result.get("message") or (
            task.get("status", {}) or {}).get("message", {})
        text = _text_from_parts((message or {}).get("parts", []))
        if text:
            return text
        for artifact in task.get("artifacts", []) or []:
            text = _text_from_parts(artifact.get("parts", []))
            if text:
                return text
        text = _text_from_parts(result.get("parts", []))
        return text or str(result)
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

        # Extract text and action from protobuf parts (text or structured data)
        user_text = ""
        action = ""
        for part in (message.parts if message else []):
            content = part.WhichOneof("content")
            if content == "text":
                user_text = user_text or part.text
            elif content == "data":
                d = MessageToDict(part.data)
                if isinstance(d, dict):
                    action = action or str(d.get("action", ""))
                    user_text = user_text or str(d.get("text", ""))

        logger.info(f"[{AGENT_NAME}] action={action!r} text={user_text!r}")

        combined = user_text or action

        # Detect if this message came from a peer agent (not from our own portal)
        metadata = MessageToDict(message.metadata) if message else {}
        sender_identity = metadata.get(IDENTITY_EXT_URI, {}) or {}
        # Accept both {agentIdentity:{name}} and flat {name} identity shapes
        sender_name = (sender_identity.get("agentIdentity") or sender_identity).get("name", "")
        vp_raw = ""

        # Fallback: gateway wraps outbound VP under agent-identity-credential/v1
        if not sender_name:
            sender_name, vp_raw = _extract_name_from_vp(metadata)
        is_from_peer_agent = bool(
            sender_name) and "Portal" not in sender_name and sender_name != AGENT_NAME
        # Log all incoming A2A messages — source field distinguishes portal vs peer agent
        INCOMING_LOG.append({
            "from": sender_name or "Unknown",
            "vp": vp_raw,
            "text": combined,
            "source": "agent" if is_from_peer_agent else "portal",
            "headers": request_headers_ctx.get(),
            "exchange": exchange_ctx.get(),
            "at": datetime.now().isoformat(),
        })
        if len(INCOMING_LOG) > 100:
            INCOMING_LOG.pop(0)

        from_peer = False

        if _should_forward(combined):
            outbound: dict = {"request": None, "response": None}
            # Log the outbound forward (even if it fails) so the agent log shows it sent to peer
            INCOMING_LOG.append({
                "from": AGENT_NAME,
                "to": PEER_AGENT_NAME,
                "text": _extract_forward_text(combined),
                "source": "forwarded",
                "headers": {},
                "vp": "",
                "exchange": outbound,
                "at": datetime.now().isoformat(),
            })
            peer_data = await _forward_to_peer(combined, auth_header, outbound)
            peer_reply = _extract_reply_text(peer_data)
            reply_text = f"[Forwarded to {PEER_AGENT_NAME}]\n\n{PEER_AGENT_NAME} says:\n{peer_reply}"
            from_peer = True
        else:
            reply_text = _mock_response(
                combined) if combined else f"Hello from {AGENT_NAME}!"

        identity = get_agent_identity(AGENT_NAME)
        identity["agentIdentity"]["fromPeer"] = from_peer
        identity["agentIdentity"]["peerName"] = PEER_AGENT_NAME if from_peer else None

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if context.current_task is None:
            await event_queue.enqueue_event(new_task_from_user_message(message))
        await updater.start_work()
        reply = updater.new_agent_message(
            [Part(text=reply_text)],
            metadata={IDENTITY_EXT_URI: identity},
        )
        reply.extensions.append(IDENTITY_EXT_URI)
        await updater.complete(reply)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()


# ── Combined ASGI middleware: auth header extraction + path rewriting ─────────
class _A2AMiddleware:
    """Rewrites /a2a/tasks/send → / so a2a-sdk handler receives the request."""

    def __init__(self, app):
        self._app = app

    @staticmethod
    async def _buffer_body(receive):
        chunks, more = [], True
        while more:
            event = await receive()
            if event["type"] == "http.disconnect":
                break
            chunks.append(event.get("body", b""))
            more = event.get("more_body", False)
        body = b"".join(chunks)
        sent = False

        async def replay():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        return body, replay

    @staticmethod
    def _restore_version_header(scope, body: bytes):
        """Gateways may strip A2A-Version. A v1 method name (no slash, e.g.
        SendMessage) is unambiguous, so restore the header when it is missing
        or says 0.3."""
        headers = dict(scope.get("headers", []))
        if headers.get(b"a2a-version", b"").decode().strip() == PROTOCOL_VERSION:
            return scope
        try:
            method = json.loads(body).get("method", "")
        except Exception:
            method = ""
        if isinstance(method, str) and method and "/" not in method:
            scope = dict(scope)
            scope["headers"] = [
                (k, v) for k, v in scope["headers"] if k.lower() != b"a2a-version"
            ] + [(b"a2a-version", PROTOCOL_VERSION.encode())]
            logger.info("Restored missing A2A-Version header for v1 method %s", method)
        return scope

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
            # Request/response bodies are captured for the portal's Agent Log view
            exchange: dict = {"request": None, "response": None}
            if scope.get("method") == "POST":
                body, receive = await self._buffer_body(receive)
                scope = self._restore_version_header(scope, body)
                exchange["request"] = _parse_json(body)
                inner_send = send
                response_chunks: list[bytes] = []

                async def send(message):
                    if message["type"] == "http.response.body":
                        response_chunks.append(message.get("body", b""))
                        if not message.get("more_body", False):
                            exchange["response"] = _parse_json(b"".join(response_chunks))
                    await inner_send(message)

            token = auth_header_ctx.set(auth)
            # Collect gateway-injected x-* headers for forwarding on outbound calls
            gateway_dict = {
                k: v for k, v in headers_dict.items() if k.lower().startswith("x-")}
            token2 = request_headers_ctx.set(headers_dict)
            token3 = gateway_headers_ctx.set(gateway_dict)
            token4 = exchange_ctx.set(exchange)
            if A2A_LEGACY_MODE and scope.get("path") == "/a2a/tasks/send":
                scope = dict(scope)
                scope["path"] = "/"
                scope["raw_path"] = b"/"
            try:
                await self._app(scope, receive, send)
            finally:
                auth_header_ctx.reset(token)
                request_headers_ctx.reset(token2)
                gateway_headers_ctx.reset(token3)
                exchange_ctx.reset(token4)
        else:
            await self._app(scope, receive, send)


# ── Build and run ─────────────────────────────────────────────────────────────
def _build_agent_card() -> AgentCard:
    card_kwargs = dict(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        supported_interfaces=_supported_interfaces(),
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
    return AgentCard(**card_kwargs)


def _supported_interfaces() -> list[AgentInterface]:
    base_url = PUBLIC_BASE_URL.rstrip("/")
    v1 = AgentInterface(
        url=base_url,
        protocol_binding=JSONRPC_BINDING,
        protocol_version=PROTOCOL_VERSION,
    )
    if not A2A_LEGACY_MODE:
        return [v1]
    # First 0.3 interface becomes the card's legacy top-level url/protocolVersion
    v03 = AgentInterface(
        url=base_url + "/",
        protocol_binding=JSONRPC_BINDING,
        protocol_version=LEGACY_PROTOCOL_VERSION,
    )
    return [v03, v1]


def main() -> None:
    logger.info("=" * 60)
    logger.info(f"Agent : {AGENT_NAME}")
    logger.info(f"Port  : {AGENT_PORT}")
    logger.info(
        f"Protocol: {'A2A 1.0 + v0.3 compat (legacy)' if A2A_LEGACY_MODE else 'A2A 1.0 only'}")
    logger.info(f"Peer  : {PEER_AGENT_NAME} @ {PEER_AGENT_URL or '(not set)'}")
    logger.info(
        f"Card  : {PUBLIC_BASE_URL.rstrip('/')}/.well-known/agent-card.json")
    logger.info("=" * 60)

    agent_card = _build_agent_card()
    request_handler = DefaultRequestHandler(
        agent_executor=SecureAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    async def health(request):
        return JSONResponse({
            "status": "healthy",
            "agent": AGENT_NAME,
            "protocolVersion": PROTOCOL_VERSION,
            "legacyCompat": A2A_LEGACY_MODE,
            "agentCard": f"{PUBLIC_BASE_URL.rstrip('/')}/.well-known/agent-card.json",
        })

    async def incoming(request):
        return JSONResponse({"messages": INCOMING_LOG})

    async def clear_incoming(request):
        INCOMING_LOG.clear()
        return JSONResponse({"ok": True})

    routes = [
        *create_agent_card_routes(agent_card),
        *create_jsonrpc_routes(
            request_handler, "/", enable_v0_3_compat=A2A_LEGACY_MODE),
        Route("/health", health, methods=["GET"]),
        Route("/incoming", incoming, methods=["GET"]),
        Route("/incoming", clear_incoming, methods=["DELETE"]),
    ]
    if A2A_LEGACY_MODE:
        # v0.3 clients may still discover the card at the pre-0.3 path
        routes.extend(create_agent_card_routes(
            agent_card, card_url="/.well-known/agent.json"))
    a2a_app = Starlette(routes=routes)

    uvicorn.run(
        _A2AMiddleware(a2a_app),
        host="0.0.0.0",
        port=AGENT_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
