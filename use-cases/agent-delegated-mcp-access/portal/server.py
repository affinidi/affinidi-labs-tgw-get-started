#!/usr/bin/env python3
"""Portal for the GitHub MCP lab.

A confidential OAuth client: signs the user in with Entra (authorization code),
keeps the access token server-side, and relays A2A messages to the Personal Agent.
The browser never sees the Entra token. The page also reads the agent's
/debug/trace to show each MCP call the agent made through the gateway.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

STATIC_DIR = Path(__file__).parent / "static"
CALLBACK_PATH = "/api/auth/callback/microsoft"
SESSION_COOKIE = "github_mcp_portal_session"
STATE_COOKIE = "github_mcp_portal_state"
SHOWN_CLAIMS = ("aud", "scp", "oid", "name", "preferred_username", "upn", "appid", "iss")
MAX_PROMPT = 2000

_SESSIONS: dict[str, "Session"] = {}


@dataclass
class Session:
    access_token: str
    expires_at: float
    name: str
    email: str


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _base_url(request: Request | None = None) -> str:
    return (_env("PORTAL_URL") or f"http://localhost:{_env('PORTAL_PORT', '8097')}").rstrip("/")


def _secure_cookies(request: Request | None = None) -> bool:
    return _base_url(request).startswith("https://")


def _scopes() -> str:
    return f"openid profile email {_env('USER_TOKEN_AUDIENCE')}/{_env('USER_TOKEN_SCOPE', 'agent.access')}"


def _agent_url() -> str:
    return (_env("AGENT_GATEWAY_URL") or _env("AGENT_PUBLIC_URL") or f"http://localhost:{_env('AGENT_PORT', '10004')}").rstrip("/")


def _agent_local_url() -> str:
    return f"http://localhost:{_env('AGENT_PORT', '10004')}"


def _claims(token: str) -> dict:
    """Display only - the agent verifies every token it receives."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:  # noqa: BLE001
        return {}


def _session(request: Request) -> Session | None:
    sid = request.cookies.get(SESSION_COOKIE)
    session = _SESSIONS.get(sid or "")
    if session and session.expires_at <= time.time():
        _SESSIONS.pop(sid, None)
        return None
    return session


async def index(_r: Request) -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


async def config(_r: Request) -> JSONResponse:
    return JSONResponse(
        {
            "configured": bool(_env("PORTAL_CLIENT_ID") and _env("PORTAL_CLIENT_SECRET")),
            "agentUrl": _agent_url(),
            "agentName": _env("AGENT_NAME") or "Personal Agent",
            "agentViaGateway": bool(_env("AGENT_GATEWAY_URL")),
            "mcpUrl": _env("MCP_GATEWAY_URL") or _env("MCP_URL"),
            "mcpViaGateway": bool(_env("MCP_GATEWAY_URL")),
        }
    )


async def auth_start(request: Request) -> Response:
    if not (_env("PORTAL_CLIENT_ID") and _env("PORTAL_CLIENT_SECRET")):
        return RedirectResponse("/?error=oauth_not_configured", status_code=302)
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": _env("PORTAL_CLIENT_ID"),
        "redirect_uri": f"{_base_url(request)}{CALLBACK_PATH}",
        "response_type": "code",
        "response_mode": "query",
        "scope": _scopes(),
        "state": state,
        "prompt": "select_account",
    }
    url = (
        f"https://login.microsoftonline.com/{_env('ENTRA_TENANT_ID')}"
        f"/oauth2/v2.0/authorize?{urlencode(params)}"
    )
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        STATE_COOKIE, state, max_age=600, httponly=True, samesite="lax", secure=_secure_cookies(request)
    )
    return response


async def auth_callback(request: Request) -> Response:
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    expected = request.cookies.get(STATE_COOKIE)

    def fail(reason: str) -> Response:
        response = RedirectResponse(f"/?error={reason}", status_code=302)
        response.delete_cookie(STATE_COOKIE)
        return response

    if request.query_params.get("error") or not code:
        return fail("auth_cancelled")
    if not state or not expected or not secrets.compare_digest(state, expected):
        return fail("state_mismatch")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_response = await client.post(
                f"https://login.microsoftonline.com/{_env('ENTRA_TENANT_ID')}/oauth2/v2.0/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": _env("PORTAL_CLIENT_ID"),
                    "client_secret": _env("PORTAL_CLIENT_SECRET"),
                    "redirect_uri": f"{_base_url(request)}{CALLBACK_PATH}",
                    "scope": _scopes(),
                },
            )
    except httpx.HTTPError:
        return fail("token_exchange_failed")
    if token_response.status_code != 200:
        print(f"[portal] token exchange failed: {token_response.text[:500]}", file=sys.stderr)
        return fail("token_exchange_failed")

    tokens = token_response.json()
    id_claims = _claims(tokens.get("id_token", ""))
    sid = secrets.token_urlsafe(32)
    expires_in = int(tokens.get("expires_in") or 3600)
    _SESSIONS[sid] = Session(
        access_token=tokens["access_token"],
        expires_at=time.time() + expires_in,
        name=str(id_claims.get("name", "")),
        email=str(id_claims.get("preferred_username") or id_claims.get("email") or ""),
    )
    if _env("PORTAL_SHOW_TOKEN", "true").lower() == "true":
        # Lab helper: raw Entra JWT for manual curl tests against the gateway.
        print(f"[portal] ENTRA_ACCESS_TOKEN={tokens['access_token']}", file=sys.stderr, flush=True)
    response = RedirectResponse("/?signedIn=1", status_code=302)
    response.set_cookie(
        SESSION_COOKIE, sid, max_age=expires_in, httponly=True, samesite="lax", secure=_secure_cookies(request)
    )
    response.delete_cookie(STATE_COOKIE)
    return response


async def me(request: Request) -> JSONResponse:
    session = _session(request)
    if not session:
        return JSONResponse({"signedIn": False})
    claims = _claims(session.access_token)
    return JSONResponse(
        {
            "signedIn": True,
            "name": session.name,
            "email": session.email,
            "userToken": {k: claims[k] for k in SHOWN_CLAIMS if k in claims},
        }
    )


async def token(request: Request) -> JSONResponse:
    """Lab helper: reveal the Entra access token this portal holds for the user."""
    if _env("PORTAL_SHOW_TOKEN", "true").lower() != "true":
        return JSONResponse({"error": "disabled"}, status_code=404)
    session = _session(request)
    if not session:
        return JSONResponse({"signedIn": False}, headers={"Cache-Control": "no-store"})
    return JSONResponse(
        {
            "signedIn": True,
            "accessToken": session.access_token,
            "expiresAt": int(session.expires_at),
            "claims": _claims(session.access_token),
        },
        headers={"Cache-Control": "no-store"},
    )


async def logout(request: Request) -> JSONResponse:
    _SESSIONS.pop(request.cookies.get(SESSION_COOKIE, ""), None)
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


async def chat(request: Request) -> JSONResponse:
    # No sign-in gate here: the gateway enforces auth and its 401 is relayed back.
    session = _session(request)
    try:
        body = await request.json()
    except ValueError:
        body = {}
    text = str(body.get("text", "") if isinstance(body, dict) else "")[:MAX_PROMPT]

    payload = {
        "jsonrpc": "2.0",
        "id": uuid.uuid4().hex[:8],
        "method": "SendMessage",
        "params": {
            "message": {
                "messageId": uuid.uuid4().hex,
                "role": "ROLE_USER",
                "parts": [{"text": text}],
            }
        },
    }
    headers = {
        "Content-Type": "application/json",
        "A2A-Version": "1.0",
    }
    if session:
        headers["Authorization"] = "Bearer " + session.access_token
    url = _agent_url()
    sent = {
        "method": "POST",
        "url": url,
        "headers": {
            **headers,
            **({"Authorization": "Bearer <redacted>"} if "Authorization" in headers else {}),
        },
        "body": payload,
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as error:
        return JSONResponse(
            {"error": "agent_unreachable", "detail": str(error), "request": sent}, status_code=502
        )
    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text[:4000]}
    return JSONResponse(
        {
            "url": url,
            "status": response.status_code,
            "headers": {
                k: v for k, v in response.headers.items() if k.lower() not in {"set-cookie"}
            },
            "body": data,
            "request": sent,
        }
    )


async def trace(request: Request) -> JSONResponse:
    try:
        since = max(0, int(request.query_params.get("since", "0")))
    except ValueError:
        since = 0
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            data = (await client.get(f"{_agent_local_url()}/debug/trace", params={"since": since})).json()
    except Exception:  # noqa: BLE001
        data = {"events": [], "cursor": since}
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


def create_app() -> Starlette:
    return Starlette(
        routes=[
            Route("/", index),
            Route("/config", config),
            Route("/api/auth/microsoft", auth_start),
            Route(CALLBACK_PATH, auth_callback),
            Route("/api/auth/me", me),
            Route("/api/auth/token", token),
            Route("/api/auth/logout", logout, methods=["POST"]),
            Route("/api/chat", chat, methods=["POST"]),
            Route("/api/trace", trace),
        ]
    )


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(_env("PORTAL_PORT", "8097"))
    uvicorn.run(create_app(), host="0.0.0.0", port=port)
