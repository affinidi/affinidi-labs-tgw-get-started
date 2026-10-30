#!/usr/bin/env python3
"""A2A v1.0 app wiring, bearer-auth middleware and a small in-memory trace that
the portal reads to show what happened."""

from __future__ import annotations

import itertools
import os
from collections import deque
from datetime import datetime, timezone

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    DefaultServerCallContextBuilder,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentExtension,
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    HTTPAuthSecurityScheme,
    SecurityRequirement,
    SecurityScheme,
    StringList,
)

from entra_auth import EntraTokenValidator, TokenError, decode_unverified, summarize_claims

CARD_PATH = "/.well-known/agent-card.json"
HEALTH_PATH = "/health"
TRACE_PATH = "/debug/trace"
PUBLIC_PATHS = frozenset({CARD_PATH, HEALTH_PATH, TRACE_PATH})

LOG_RAW_TOKEN = os.environ.get("LOG_RAW_TOKEN", "").strip().lower() in {"1", "true", "yes"}

_TRACE: deque[dict] = deque(maxlen=200)
_SEQ = itertools.count(1)


def record(kind: str, **fields) -> dict:
    event = {
        "seq": next(_SEQ),
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "kind": kind,
        **fields,
    }
    _TRACE.append(event)
    return event


def token_view(token: str) -> dict:
    """Token description safe for logs: claims always, raw JWT only on opt-in."""
    view = {"claims": summarize_claims(decode_unverified(token))}
    if LOG_RAW_TOKEN:
        view["raw"] = token
    return view


IDENTITY_EXTENSION_URI = "https://fabric.affinidi.io/extensions/agent-identity/v1"


def create_card(
    *,
    name: str,
    description: str,
    base_url: str,
    skill: AgentSkill,
    scheme_note: str,
    identity: dict[str, str],
) -> AgentCard:
    return AgentCard(
        name=name,
        description=description,
        version="1.0.0",
        supported_interfaces=[
            AgentInterface(url=base_url, protocol_binding="JSONRPC", protocol_version="1.0")
        ],
        capabilities=AgentCapabilities(
            streaming=False,
            extensions=[
                AgentExtension(
                    uri=IDENTITY_EXTENSION_URI,
                    description="Agent identity metadata (name, role, model).",
                    required=False,
                    params=identity,
                )
            ],
        ),
        security_schemes={
            "entra_bearer": SecurityScheme(
                http_auth_security_scheme=HTTPAuthSecurityScheme(
                    scheme="bearer", bearer_format="JWT", description=scheme_note
                )
            )
        },
        security_requirements=[
            SecurityRequirement(schemes={"entra_bearer": StringList(list=[])})
        ],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[skill],
    )


class TokenContextBuilder:
    """Carries the verified token and claims into the A2A call context."""

    def __init__(self) -> None:
        self._inner = DefaultServerCallContextBuilder()

    def build(self, request: Request):
        context = self._inner.build(request)
        context.state["token"] = request.scope.get("bearer_token", "")
        context.state["claims"] = request.scope.get("bearer_claims", {})
        # Set by the gateway when the call arrived through its agent access point.
        context.state["transit_token"] = request.headers.get("x-transit-token", "")
        return context


def _auth_middleware(validator: EntraTokenValidator, agent_label: str):
    async def middleware(request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        try:
            token = validator.extract_bearer(request.headers.get("authorization"))
            claims = validator.validate(token)
        except TokenError as error:
            record(
                "rejected",
                agent=agent_label,
                reason=error.reason,
                detail=error.detail,
                claims=summarize_claims(
                    decode_unverified(request.headers.get("authorization", "")[7:])
                ),
            )
            print(f"[{agent_label}] REJECTED {error.reason}: {error.detail}", flush=True)
            return JSONResponse(
                {"error": {"code": error.reason, "message": error.detail}},
                status_code=401,
                headers={"WWW-Authenticate": f'Bearer error="{error.reason}"'},
            )
        request.scope["bearer_token"] = token
        request.scope["bearer_claims"] = claims
        if getattr(validator, "validates", True):
            record("accepted", agent=agent_label, claims=summarize_claims(claims))
            status = "ACCEPTED"
        else:
            record(
                "passthrough",
                agent=agent_label,
                token_present=bool(token),
                transit_token_present=bool(request.headers.get("x-transit-token")),
                header_names=sorted(request.headers.keys()),
                claims=summarize_claims(claims),
            )
            status = "PASSTHROUGH (not validated)" if token else "PASSTHROUGH (no token)"
        print(
            f"[{agent_label}] {status} user={claims.get('name') or claims.get('oid')} "
            f"aud={claims.get('aud')} scp={claims.get('scp')} "
            f"appid={claims.get('appid')}",
            flush=True,
        )
        return await call_next(request)

    return middleware


def create_app(
    *,
    card: AgentCard,
    executor: AgentExecutor,
    validator: EntraTokenValidator,
    agent_label: str,
) -> Starlette:
    handler = DefaultRequestHandler(
        agent_executor=executor, task_store=InMemoryTaskStore(), agent_card=card
    )

    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy", "agent": agent_label})

    async def trace(request: Request) -> JSONResponse:
        try:
            since = int(request.query_params.get("since", "0"))
        except ValueError:
            since = 0
        events = [event for event in _TRACE if event["seq"] > since]
        return JSONResponse(
            {"events": events, "cursor": _TRACE[-1]["seq"] if _TRACE else since},
            headers={"Cache-Control": "no-store"},
        )

    origins = [
        o.strip()
        for o in os.environ.get("PORTAL_URL", "http://localhost:8097").split(",")
        if o.strip()
    ]
    return Starlette(
        routes=[
            *create_agent_card_routes(card, card_url=CARD_PATH),
            *create_jsonrpc_routes(handler, "/", context_builder=TokenContextBuilder()),
            Route(HEALTH_PATH, health, methods=["GET"]),
            # Lab only: the trace lists claims (never raw tokens unless LOG_RAW_TOKEN).
            Route(TRACE_PATH, trace, methods=["GET"]),
        ],
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=origins,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Authorization", "Content-Type", "A2A-Version", "X-Transit-Token"],
            ),
            Middleware(BaseHTTPMiddleware, dispatch=_auth_middleware(validator, agent_label)),
        ],
    )
