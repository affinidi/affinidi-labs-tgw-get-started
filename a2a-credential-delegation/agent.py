#!/usr/bin/env python3
"""A2A v1.0 echo agent protected by Microsoft Entra ID bearer tokens.

Two things make this lab different from the plain `a2a-v1` lab:

1. The agent card is published on a custom path,
   `/protocols/a2a/agentCard/v1.0`, instead of the well-known path.
2. Every JSON-RPC call must carry a valid Entra access token. Calls without a
   token, or with a token this agent does not trust, are rejected with 401.

The agent itself does no LLM work -- it echoes the caller's text back.
"""

from __future__ import annotations

import itertools
import os
import sys
from collections import deque
from datetime import datetime, timezone

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.helpers.proto_helpers import new_task_from_user_message
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentExtension,
    AgentInterface,
    AgentSkill,
    HTTPAuthSecurityScheme,
    Part,
    SecurityRequirement,
    SecurityScheme,
    StringList,
)

from entra_auth import (
    EntraConfigError,
    EntraTokenValidator,
    TokenError,
    describe_caller,
    format_token_log,
    inspect_token,
    load_settings,
)


PROTOCOL_VERSION = "1.0"
JSONRPC_BINDING = "JSONRPC"
IDENTITY_EXTENSION_URI = "https://fabric.affinidi.io/extensions/agent-identity/v1"

AGENT_CARD_PATH = "/protocols/a2a/agentCard/v1.0"
JSONRPC_PATH = "/"
HEALTH_PATH = "/health"
EVENTS_PATH = "/debug/events"

# The card and health endpoints stay open so that a gateway or client can
# discover the agent and learn which credential it needs. Everything else,
# including the JSON-RPC endpoint, requires a valid Entra token.
#
# /debug/events is open too so the lab portal can show traffic from any
# client, including unauthenticated ones. It exposes presented tokens: this
# is a local lab only -- never expose this endpoint on a real deployment.
PUBLIC_PATHS = frozenset({AGENT_CARD_PATH, HEALTH_PATH, EVENTS_PATH})

ENTRA_SECURITY_SCHEME = "entra_bearer"

# Bounded in-memory event log. Every A2A call the agent sees lands here,
# whoever made it, so the portal can show traffic from other clients too.
EVENT_LOG_SIZE = 500
_EVENTS: deque[dict] = deque(maxlen=EVENT_LOG_SIZE)
_EVENT_SEQ = itertools.count(1)


def record_event(kind: str, **fields) -> dict:
    event = {
        "seq": next(_EVENT_SEQ),
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "kind": kind,
        **fields,
    }
    _EVENTS.append(event)
    return event


MAX_LOGGED_BODY = 16_000


def decode_body(raw: bytes) -> str:
    if not raw:
        return ""
    text = raw[:MAX_LOGGED_BODY].decode("utf-8", errors="replace")
    return text + ("\n…truncated…" if len(raw) > MAX_LOGGED_BODY else "")


def describe_response(response, body: bytes) -> dict:
    return {
        "status": response.status_code,
        "headers": dict(response.headers),
        "body": decode_body(body),
    }


def get_agent_identity() -> dict[str, str]:
    return {
        "name": "A2A v1 Entra Echo Agent",
        "model": "echo",
        "role": "A2A v1 Entra-protected test agent",
        "version": "1.0.0",
    }


class EchoAgentExecutor(AgentExecutor):
    """Completes each task with an echo of its text input."""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if context.current_task is None:
            await event_queue.enqueue_event(
                new_task_from_user_message(context.message)
            )
        await updater.start_work()

        caller = (context.call_context.state.get("entra_caller") or {}) if (
            context.call_context
        ) else {}
        greeting = caller.get("display") or "authenticated caller"
        caller_type = caller.get("callerType") or "unknown"

        response = updater.new_agent_message(
            [
                Part(
                    text=(
                        f"Echo from A2A v1.0 Entra agent (verified {caller_type}: "
                        f"{greeting}): {context.get_user_input()}"
                    )
                )
            ],
            metadata={IDENTITY_EXTENSION_URI: get_agent_identity()},
        )
        response.extensions.append(IDENTITY_EXTENSION_URI)
        await updater.complete(response)

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()


def create_agent_card(public_base_url: str, required_scope: str | None) -> AgentCard:
    """Create a v1 agent card that declares its Entra bearer requirement."""
    scheme_description = (
        "Microsoft Entra ID access token presented as 'Authorization: Bearer "
        "<token>'. Requests without a valid token are rejected with HTTP 401."
    )
    return AgentCard(
        name="A2A v1 Entra Echo Agent",
        description=(
            "An A2A v1.0 echo agent protected by Microsoft Entra ID bearer "
            "tokens, publishing its card on a custom path."
        ),
        version="1.0.0",
        supported_interfaces=[
            AgentInterface(
                url=public_base_url,
                protocol_binding=JSONRPC_BINDING,
                protocol_version=PROTOCOL_VERSION,
            )
        ],
        capabilities=AgentCapabilities(
            streaming=False,
            extensions=[
                AgentExtension(
                    uri=IDENTITY_EXTENSION_URI,
                    description="Returns identity metadata for the A2A test agent.",
                    required=False,
                    params=get_agent_identity(),
                )
            ],
        ),
        security_schemes={
            ENTRA_SECURITY_SCHEME: SecurityScheme(
                http_auth_security_scheme=HTTPAuthSecurityScheme(
                    description=scheme_description,
                    scheme="bearer",
                    bearer_format="JWT",
                )
            )
        },
        security_requirements=[
            SecurityRequirement(
                schemes={
                    ENTRA_SECURITY_SCHEME: StringList(
                        list=[required_scope] if required_scope else []
                    )
                }
            )
        ],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id="echo",
                name="Echo",
                description="Returns the text supplied by the authenticated caller.",
                tags=["test", "echo", "entra"],
                examples=["Hello, Agent Gateway"],
            )
        ],
    )


def unauthorized(reason: str, detail: str) -> JSONResponse:
    """Build a 401 that tells the caller what credential is expected."""
    return JSONResponse(
        {
            "error": {
                "code": reason,
                "message": detail,
                "expected": "Authorization: Bearer <Microsoft Entra ID token>",
                "agentCardUrl": AGENT_CARD_PATH,
            }
        },
        status_code=401,
        headers={
            "WWW-Authenticate": (
                f'Bearer realm="a2a-credential-delegation", error="{reason}", '
                f'error_description="{detail}"'
            )
        },
    )


def build_auth_middleware(validator: EntraTokenValidator):
    """Reject every non-public request that lacks a valid Entra token."""

    log_raw_token = os.environ.get("LOG_RAW_TOKEN", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    def readable_headers(headers) -> dict[str, str]:
        out = {}
        for key, value in headers.items():
            if key.lower() == "authorization" and not log_raw_token:
                out[key] = "Bearer <redacted, set LOG_RAW_TOKEN=true to show>"
            else:
                out[key] = value
        return out

    async def entra_auth_middleware(request: Request, call_next):
        # CORS preflight carries no Authorization header by design.
        if request.method == "OPTIONS":
            return await call_next(request)
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        request_body = await request.body()
        exchange = {
            "request": {
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query or ""),
                "client": request.client.host if request.client else "-",
                "headers": readable_headers(request.headers),
                "body": decode_body(request_body),
            }
        }

        def finish(response, **extra) -> None:
            record_event(
                extra.pop("kind", "call"),
                **exchange,
                response={
                    "status": response.status_code,
                    "headers": dict(response.headers),
                    "body": None,  # filled in by the caller when available
                },
                **extra,
            )

        authorization = request.headers.get("authorization")
        try:
            token = validator.extract_bearer(authorization)
        except TokenError as error:
            response = unauthorized(error.reason, error.detail)
            record_event(
                "rejected",
                **exchange,
                response=describe_response(response, response.body),
                reason=error.reason,
                detail=error.detail,
            )
            print(
                f"Rejected A2A call: {error.reason} - {error.detail}", flush=True)
            return response

        # Captured before validation so a rejected token can still be inspected.
        token_report = inspect_token(token)
        if log_raw_token:
            token_report["raw"] = token
        exchange["token"] = token_report
        print(
            "Bearer token presented:\n"
            + format_token_log(token, include_raw=log_raw_token),
            flush=True,
        )

        try:
            claims = validator.validate(token)
        except TokenError as error:
            response = unauthorized(error.reason, error.detail)
            record_event(
                "rejected",
                **exchange,
                response=describe_response(response, response.body),
                reason=error.reason,
                detail=error.detail,
            )
            print(
                f"Rejected A2A call: {error.reason} - {error.detail}", flush=True)
            return response

        caller = describe_caller(claims)
        request.scope["entra_caller"] = caller
        print(
            f"Authorized A2A call from {caller['display']} "
            f"[{caller['callerType']} via {caller['flow']}] "
            f"(tenant {caller['tenant']})",
            flush=True,
        )

        response = await call_next(request)
        # The downstream response streams, so it is drained here and replayed
        # to the client in order to log its body.
        body = b"".join([chunk async for chunk in response.body_iterator])
        record_event(
            "authorized",
            **exchange,
            caller=caller,
            response=describe_response(response, body),
        )
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    return entra_auth_middleware


class EntraContextBuilder:
    """Carries the verified caller into the A2A ServerCallContext."""

    def __init__(self, inner) -> None:
        self._inner = inner

    def build(self, request: Request):
        context = self._inner.build(request)
        context.state["entra_caller"] = request.scope.get("entra_caller", {})
        return context


def create_app(port: int) -> Starlette:
    settings = load_settings()
    validator = EntraTokenValidator(settings)

    public_base_url = os.environ.get(
        "PUBLIC_BASE_URL", f"http://localhost:{port}"
    ).rstrip("/")
    agent_card = create_agent_card(public_base_url, settings.required_scope)

    from a2a.server.routes import DefaultServerCallContextBuilder

    request_handler = DefaultRequestHandler(
        agent_executor=EchoAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    async def health_check(_request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "healthy",
                "protocol_version": PROTOCOL_VERSION,
                "agent_card_url": f"{public_base_url}{AGENT_CARD_PATH}",
                "auth": "microsoft-entra-id",
                "tenant": settings.tenant_id,
            }
        )

    async def events(request: Request) -> JSONResponse:
        if request.method == "DELETE":
            _EVENTS.clear()
            # The sequence keeps counting, so open viewers never replay old ids.
            return JSONResponse({"ok": True})

        try:
            since = int(request.query_params.get("since", "0"))
        except ValueError:
            since = 0
        pending = [event for event in _EVENTS if event["seq"] > since]
        return JSONResponse(
            {
                "events": pending,
                "cursor": _EVENTS[-1]["seq"] if _EVENTS else since,
            },
            headers={"Cache-Control": "no-store"},
        )

    routes = [
        *create_agent_card_routes(agent_card, card_url=AGENT_CARD_PATH),
        *create_jsonrpc_routes(
            request_handler,
            JSONRPC_PATH,
            context_builder=EntraContextBuilder(
                DefaultServerCallContextBuilder()),
        ),
        Route(HEALTH_PATH, health_check, methods=["GET"]),
        Route(EVENTS_PATH, events, methods=["GET", "DELETE"]),
    ]

    # The browser portal is a separate origin, so it needs an explicit allow
    # list. Keep it to the configured portal origins -- never "*" on an
    # authenticated endpoint.
    allowed_origins = [
        origin.strip()
        for origin in os.environ.get(
            "PORTAL_ORIGINS", "http://localhost:8095"
        ).split(",")
        if origin.strip()
    ]

    # CORS is listed first so it stays outermost and 401 responses produced by
    # the auth middleware still carry the headers the browser needs to read them.
    return Starlette(
        routes=routes,
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=allowed_origins,
                allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                allow_headers=[
                    "Authorization",
                    "Content-Type",
                    "A2A-Version",
                    "A2A-Extensions",
                ],
                max_age=600,
            ),
            Middleware(
                BaseHTTPMiddleware, dispatch=build_auth_middleware(validator)
            ),
        ],
    )


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 10002
    try:
        app = create_app(port)
    except EntraConfigError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
