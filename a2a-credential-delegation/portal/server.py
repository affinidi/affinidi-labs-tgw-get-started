#!/usr/bin/env python3
"""Portal for the Entra-protected A2A v1 echo agent.

This portal is a *confidential* OAuth client, mirroring
use-cases/secure-agent-communication/portal:

  1. /api/auth/microsoft           -> redirects the browser to Entra
  2. /api/auth/callback/microsoft  -> exchanges the code for tokens using the
                                      client secret (server side only)
  3. /api/auth/token               -> hands the access token to the browser so
                                      the page can call the agent directly

The client secret never leaves the server and the authorization code is only
ever exchanged here. The session id lives in an httpOnly, SameSite=Lax cookie.

NOTE: because the browser talks to the agent directly (A2A JSON-RPC straight
from the page to AGENT_URL), the access token is handed to page JavaScript.
That is a deliberate lab trade-off to make the wire traffic observable; it
means any XSS in this portal can exfiltrate the token. Keep the token in
memory only -- never in localStorage -- and keep the TTL short.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route


STATIC_DIR = Path(__file__).parent / "static"

CALLBACK_PATH = "/api/auth/callback/microsoft"
SESSION_COOKIE = "a2a_portal_session"
STATE_COOKIE = "a2a_portal_oauth_state"
AGENT_CARD_PATH = "/protocols/a2a/agentCard/v1.0"
# The gateway republishes each agent's card on the A2A well-known path.
GATEWAY_CARD_PATH = "/.well-known/agent-card.json"

# Lab-local session store. A real deployment would use a shared, persistent
# store; keeping tokens server-side is the point, not the storage engine.
_SESSIONS: dict[str, "Session"] = {}


@dataclass
class Session:
    access_token: str
    expires_at: float
    email: str
    name: str


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _portal_base_url() -> str:
    port = _env("PORTAL_PORT", "8095") or "8095"
    return (_env("PORTAL_PUBLIC_URL") or f"http://localhost:{port}").rstrip("/")


def _redirect_uri() -> str:
    return _env("ENTRA_REDIRECT_URI") or f"{_portal_base_url()}{CALLBACK_PATH}"


def _tenant_id() -> str:
    return _env("MICROSOFT_TENANT_ID") or _env("ENTRA_TENANT_ID") or "common"


def _client_id() -> str:
    return _env("MICROSOFT_CLIENT_ID") or _env("ENTRA_CLIENT_ID")


def _client_secret() -> str:
    return _env("MICROSOFT_CLIENT_SECRET")


def _scopes() -> str:
    """Scopes requested from Entra.

    The agent's API scope is requested explicitly. Mixing `/.default` with
    `openid`/`profile` makes Entra reject the request with `invalid_request`.
    """
    scopes = ["openid", "profile", "email"]
    app_id_uri = _env("ENTRA_APP_ID_URI")
    if app_id_uri:
        scope_name = _env("ENTRA_SCOPE_NAME", "agent.access") or "agent.access"
        scopes.append(f"{app_id_uri}/{scope_name}")
    elif api_scope := _env("ENTRA_API_SCOPE"):
        scopes.append(api_scope)
    return " ".join(scopes)


def _agent_url() -> str:
    return (_env("AGENT_URL") or "http://localhost:10002").rstrip("/")


def _gateway_url() -> str:
    """Full gateway endpoint for the target agent, including its path."""
    return _env("GATEWAY_URL").rstrip("/")


def _gateway_user_url() -> str:
    """Gateway endpoint that runs the 3-legged user-consent flow."""
    return _env("GATEWAY_USER_CONSENT_URL").rstrip("/")


def _gateway_api_key() -> str:
    return _env("GATEWAY_API_KEY")


def _decode_jwt_claims(token: str) -> dict:
    """Read claims from a JWT *without* verifying it.

    Only ever applied to the id_token the portal just received over TLS
    directly from Entra, and only to display a name in the UI. Every
    security decision is made by the agent, which verifies the signature.
    """
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:  # noqa: BLE001 - a malformed token simply yields no name
        return {}


def _get_session(request: Request) -> Session | None:
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        return None
    session = _SESSIONS.get(session_id)
    if session is None:
        return None
    if session.expires_at <= time.time():
        _SESSIONS.pop(session_id, None)
        return None
    return session


def _clear_cookie(response: Response, name: str) -> None:
    response.delete_cookie(name, path="/")


def _set_session_cookie(response: Response, session_id: str, max_age: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=max_age,
        path="/",
        httponly=True,
        samesite="lax",
        # The lab runs on http://localhost; set this when serving over TLS.
        secure=_portal_base_url().startswith("https://"),
    )


# --- routes ------------------------------------------------------------------


async def index(_request: Request) -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


async def config_endpoint(_request: Request) -> JSONResponse:
    """Only values that are safe for the browser. No secret, no token."""
    return JSONResponse(
        {
            "agentUrl": _agent_url(),
            "agentCardPath": AGENT_CARD_PATH,
            "configured": bool(_client_id() and _client_secret() and _tenant_id()),
            "gatewayUrl": _gateway_url(),
            "gatewayCardPath": GATEWAY_CARD_PATH,
            "gatewayConfigured": bool(_gateway_url() and _gateway_api_key()),
            "gatewayUserUrl": _gateway_user_url(),
            "gatewayUserConfigured": bool(
                _gateway_user_url() and _gateway_api_key()
            ),
        }
    )


async def auth_start(_request: Request) -> Response:
    """Step 1: send the browser to Entra to sign in."""
    if not _client_id() or not _client_secret():
        return RedirectResponse("/?error=oauth_not_configured", status_code=302)

    state = secrets.token_urlsafe(32)
    params = {
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "response_mode": "query",
        "scope": _scopes(),
        "state": state,
        "prompt": "select_account",
    }
    url = (
        f"https://login.microsoftonline.com/{_tenant_id()}"
        f"/oauth2/v2.0/authorize?{urlencode(params)}"
    )

    response = RedirectResponse(url, status_code=302)
    # Bound to the browser so the callback can prove the code belongs to a
    # request this portal actually started (CSRF defence).
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=600,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_portal_base_url().startswith("https://"),
    )
    return response


async def auth_callback(request: Request) -> Response:
    """Step 2: exchange the authorization code for tokens, server side."""
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    state = request.query_params.get("state")
    expected_state = request.cookies.get(STATE_COOKIE)

    def fail(reason: str) -> Response:
        response = RedirectResponse(f"/?error={reason}", status_code=302)
        _clear_cookie(response, STATE_COOKIE)
        return response

    if error or not code:
        return fail(error or "auth_cancelled")
    if not state or not expected_state or not secrets.compare_digest(
        state, expected_state
    ):
        return fail("state_mismatch")
    if not _client_id() or not _client_secret():
        return fail("oauth_not_configured")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_response = await client.post(
                f"https://login.microsoftonline.com/{_tenant_id()}/oauth2/v2.0/token",
                data={
                    "code": code,
                    "client_id": _client_id(),
                    "client_secret": _client_secret(),
                    "redirect_uri": _redirect_uri(),
                    "grant_type": "authorization_code",
                    "scope": _scopes(),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.HTTPError:
        return fail("token_exchange_failed")

    if token_response.status_code != 200:
        # The Entra error body can contain request-identifying detail, so it is
        # logged for the operator and never returned to the browser.
        print(
            f"[portal] token exchange failed: {token_response.status_code} "
            f"{token_response.text[:500]}",
            file=sys.stderr,
        )
        return fail("token_exchange_failed")

    tokens = token_response.json()
    access_token = tokens.get("access_token")
    if not access_token:
        return fail("token_exchange_failed")

    claims = _decode_jwt_claims(tokens.get("id_token", ""))
    expires_in = int(tokens.get("expires_in") or 3600)

    session_id = secrets.token_urlsafe(32)
    _SESSIONS[session_id] = Session(
        access_token=access_token,
        expires_at=time.time() + expires_in,
        email=str(claims.get("preferred_username")
                  or claims.get("email") or ""),
        name=str(claims.get("name") or ""),
    )

    response = RedirectResponse("/?signedIn=1", status_code=302)
    _set_session_cookie(response, session_id, expires_in)
    _clear_cookie(response, STATE_COOKIE)
    return response


async def auth_me(request: Request) -> JSONResponse:
    session = _get_session(request)
    if session is None:
        return JSONResponse({"signedIn": False}, status_code=200)
    return JSONResponse(
        {"signedIn": True, "email": session.email, "name": session.name}
    )


async def auth_logout(request: Request) -> JSONResponse:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        _SESSIONS.pop(session_id, None)
    response = JSONResponse({"ok": True})
    _clear_cookie(response, SESSION_COOKIE)
    return response


async def auth_token(request: Request) -> JSONResponse:
    """Step 3: hand the signed-in session's access token to its own page.

    Only the cookie-bearing browser session can read its own token, and only
    from the portal origin (no CORS headers are emitted here, so another site
    cannot read the response even though the cookie is SameSite=Lax).
    """
    session = _get_session(request)
    if session is None:
        return JSONResponse({"error": "not_signed_in"}, status_code=401)
    return JSONResponse(
        {
            "accessToken": session.access_token,
            "expiresIn": max(0, int(session.expires_at - time.time())),
            "tokenType": "Bearer",
        },
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


async def gateway_key(_request: Request) -> JSONResponse:
    """Hand the gateway API key to the page so it can call the gateway itself.

    LAB ONLY. Unlike the short-lived Entra token, this is a long-lived shared
    secret: anyone who can run script on this origin can take it and keep it.
    A real portal would relay through /api/gateway/chat instead and never
    publish the key.
    """
    if not _gateway_api_key() or not (_gateway_url() or _gateway_user_url()):
        return JSONResponse({"error": "gateway_not_configured"}, status_code=503)
    return JSONResponse(
        {
            "gatewayUrl": _gateway_url(),
            "gatewayUserUrl": _gateway_user_url(),
            "apiKey": _gateway_api_key(),
        },
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


async def gateway_chat(request: Request) -> JSONResponse:
    """Relay one JSON-RPC call to the gateway, used when the browser cannot.

    The gateway is a third-party origin and may not send CORS headers, in
    which case the page falls back to this server-side hop. `target=user`
    selects the 3-legged user-consent route, anything else the m2m route.
    """
    target = (
        _gateway_user_url()
        if request.query_params.get("target") == "user"
        else _gateway_url()
    )
    if not target or not _gateway_api_key():
        return JSONResponse({"error": "gateway_not_configured"}, status_code=503)

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "invalid_request"}, status_code=400)
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        return JSONResponse({"error": "invalid_request"}, status_code=400)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            gateway_response = await client.post(
                target,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "A2A-Version": "1.0",
                    "Authorization": _gateway_api_key(),
                },
            )
    except httpx.HTTPError:
        return JSONResponse({"error": "gateway_unreachable"}, status_code=502)

    try:
        body = gateway_response.json()
    except ValueError:
        body = {"raw": gateway_response.text[:4000]}

    return JSONResponse(
        {
            "gatewayStatus": gateway_response.status_code,
            "gatewayHeaders": dict(gateway_response.headers),
            "gateway": body,
        }
    )


def create_app() -> Starlette:
    return Starlette(
        routes=[
            Route("/", index, methods=["GET"]),
            Route("/config", config_endpoint, methods=["GET"]),
            Route("/api/auth/microsoft", auth_start, methods=["GET"]),
            Route(CALLBACK_PATH, auth_callback, methods=["GET"]),
            Route("/api/auth/me", auth_me, methods=["GET"]),
            Route("/api/auth/logout", auth_logout, methods=["POST"]),
            Route("/api/auth/token", auth_token, methods=["GET"]),
            Route("/api/gateway/key", gateway_key, methods=["GET"]),
            Route("/api/gateway/chat", gateway_chat, methods=["POST"]),
        ]
    )


def main() -> None:
    port = (
        int(sys.argv[1])
        if len(sys.argv) > 1
        else int(os.environ.get("PORTAL_PORT", "8095"))
    )
    uvicorn.run(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
