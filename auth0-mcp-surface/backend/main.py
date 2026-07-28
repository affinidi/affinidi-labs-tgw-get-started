"""
Agent Gateway Chat — FastAPI backend (API only)

Caller context:        Google OAuth (user identity → verified by Agent Gateway)
Credential delegation: Auth0 OAuth (handled by Agent Gateway, on-demand consent)

This backend exposes a small JSON API consumed by the Astro + Alpine.js frontend.
It handles the Google OAuth login flow, keeps the user's Google id_token in a
signed session cookie, and proxies MCP requests to the Affinidi Agent Gateway.

The Agent Gateway is responsible for verifying the Google JWT (caller context)
and for delegating Auth0 credentials to the upstream MCP server on demand. When
the gateway needs consent it returns a `consent_required` payload containing an
`authorization_url`; the frontend renders that so the user can authorise.

Run:
    uvicorn main:app --reload --port 8642

Env vars (see .env.example):
    GOOGLE_CLIENT_ID       Google OAuth client ID
    GOOGLE_CLIENT_SECRET   Google OAuth client secret
    REDIRECT_URI           OAuth callback (default http://localhost:8642/api/auth/callback)
    GATEWAY_URL            Affinidi Agent Gateway MCP surface endpoint
    FRONTEND_URL           Frontend origin (default = this server's origin)
    BACKEND_URL            Public base URL for ngrok/Codespaces (sets callback + frontend)
    SESSION_SECRET         Session cookie signing secret
    PORT                   Server port (default 8642)
"""

import os
import time
import secrets
import pathlib
from urllib.parse import urlparse

import httpx
import publicsuffix2
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Configuration ────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GATEWAY_URL = os.environ.get("GATEWAY_URL", "")
PORT = int(os.environ.get("PORT", 8642))
SESSION_SECRET = os.environ.get("SESSION_SECRET", secrets.token_hex(32))

# Public base URL of THIS backend (ngrok / Codespaces / proxy). Drives the OAuth
# callback, which always lives on the backend. Falls back to localhost.
BACKEND_URL = os.environ.get("BACKEND_URL", "").rstrip("/")
_own_origin = BACKEND_URL or f"http://localhost:{PORT}"

# OAuth callback is always on this backend.
REDIRECT_URI = os.environ.get(
    "REDIRECT_URI") or f"{_own_origin}/api/auth/callback"

# Where the browser lands after login. Defaults to this backend's origin
# (single-origin: the backend serves the UI). For a SPLIT deploy — frontend and
# backend on different hosts — set FRONTEND_URL explicitly; it is independent of
# BACKEND_URL.
FRONTEND_URL = (os.environ.get("FRONTEND_URL") or _own_origin).rstrip("/")


# ── Session-cookie policy ─────────────────────────────────────────────────────
# origin ≠ site. Two subdomains of the same registrable domain (e.g.
# foo.affinidi.io and bar.affinidi.io) are cross-ORIGIN but SAME-SITE, so a
# SameSite=Lax cookie is still sent between them — we only need to widen the
# cookie's Domain to the shared parent so both hosts can see it. A genuinely
# different site requires SameSite=None; Secure instead.
def _host(url: str) -> str:
    return urlparse(url).hostname or ""


def _shared_parent(a: str, b: str) -> str:
    """
    Find the shared parent domain between two hostnames.
    Returns empty string if they share a public suffix (e.g., ngrok-free.app)
    to avoid setting cookies that browsers will reject.
    """
    common: list[str] = []
    for x, y in zip(reversed(a.split(".")), reversed(b.split("."))):
        if x != y:
            break
        common.append(x)
    common.reverse()

    if len(common) < 2:
        return ""

    shared = ".".join(common)

    # Check if shared parent is a public suffix (like ngrok-free.app, ngrok.app, etc.)
    # Browsers reject cookies on public suffixes for security reasons.
    psl = publicsuffix2.PublicSuffixList()
    if psl.get_public_suffix(shared) == shared:
        # Shared parent is itself a public suffix - can't set cookie here
        return ""

    return shared


_own_host, _fe_host = _host(_own_origin), _host(FRONTEND_URL)
COOKIE_DOMAIN = os.environ.get("SESSION_COOKIE_DOMAIN") or None
if _own_host == _fe_host:
    # Single origin — host-only cookie is fine.
    COOKIE_SAMESITE = "lax"
else:
    _parent = COOKIE_DOMAIN or _shared_parent(_own_host, _fe_host)
    if _parent:
        # Subdomains of one site: share the cookie via Domain, keep Lax.
        COOKIE_DOMAIN, COOKIE_SAMESITE = _parent, "lax"
    else:
        # Genuinely different sites: only SameSite=None; Secure works.
        COOKIE_DOMAIN, COOKIE_SAMESITE = None, "none"

_is_https = _own_origin.startswith("https") or FRONTEND_URL.startswith("https")
COOKIE_SECURE = _is_https or COOKIE_SAMESITE == "none"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

CHAT_TOOL_NAME = "chat"
AGENT_NAME = "chat-client"

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="Agent Gateway Chat API", version="1.0.0")

# Session cookie. Domain/SameSite/Secure are computed above so the cookie works
# for single-origin, shared-subdomain (Lax + Domain), and true cross-site
# (None + Secure) deployments alike.
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site=COOKIE_SAMESITE,
    https_only=COOKIE_SECURE,
    domain=COOKIE_DOMAIN,
)

# CORS for split/two-server modes (frontend on a different origin calling the
# API). In single-origin mode requests are same-origin, so CORS is a no-op.
_cors_origins = [FRONTEND_URL, _own_origin,
                 "http://localhost:5137", f"http://localhost:{PORT}"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(_cors_origins)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Server-side OAuth state store (survives cross-domain redirects) ────────────
_OAUTH_STATE_TTL = 300  # 5 minutes
_oauth_states: dict[str, float] = {}


def _put_state(state: str) -> None:
    now = time.time()
    for k in [k for k, exp in _oauth_states.items() if exp < now]:
        _oauth_states.pop(k, None)
    _oauth_states[state] = now + _OAUTH_STATE_TTL


def _pop_state(state: str) -> bool:
    if not state:
        return False
    exp = _oauth_states.pop(state, None)
    return exp is not None and exp >= time.time()


# ── MCP helpers ────────────────────────────────────────────────────────────────
def _chat_tool_request_body(message: str) -> dict:
    """Build a JSON-RPC tools/call request for the `chat` tool."""
    return {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
        "method": "tools/call",
        "params": {
            "_meta": {
                "agentIdentity": {"name": AGENT_NAME, "version": "1.0.0"}
            },
            "name": CHAT_TOOL_NAME,
            "arguments": {"message": message},
        },
    }


async def _proxy_gateway_request(
    req_headers: dict[str, str], body: dict, label: str
) -> tuple[int, dict]:
    """Forward a JSON-RPC body to the Agent Gateway and return (status, json)."""
    print(f"\n[{label}] POST {GATEWAY_URL}")
    print(f"[{label}] Headers: {req_headers}")
    print(f"[{label}] Request body: {body}")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(GATEWAY_URL, json=body, headers=req_headers)

    print(f"[{label}] Response status: {resp.status_code}")
    print(f"[{label}] Response body: {resp.text[:500]}")
    try:
        resp_body = resp.json()
    except Exception:
        resp_body = {"raw": resp.text}
    return resp.status_code, resp_body


# ── Auth routes ─────────────────────────────────────────────────────────────────
@app.get("/api/auth/login")
def login():
    """Return the Google OAuth authorization URL for the frontend to redirect to."""
    state = secrets.token_hex(16)
    _put_state(state)
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    import urllib.parse
    return {"auth_url": f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"}


@app.get("/api/auth/callback")
async def callback(request: Request):
    """Handle Google's OAuth redirect: exchange code, store token, bounce to frontend."""
    state = request.query_params.get("state", "")
    if not _pop_state(state):
        return JSONResponse({"error": "State mismatch – possible CSRF."}, status_code=400)

    error = request.query_params.get("error")
    if error:
        return JSONResponse({"error": f"OAuth error: {error}"}, status_code=400)

    code = request.query_params.get("code")
    if not code:
        return JSONResponse({"error": "No authorization code received."}, status_code=400)

    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        tokens = token_resp.json()

        if "error" in tokens:
            desc = tokens.get("error_description", tokens["error"])
            return JSONResponse({"error": f"Token exchange failed: {desc}"}, status_code=400)

        access_token = tokens.get("access_token")
        id_token = tokens.get("id_token")

        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        userinfo = userinfo_resp.json()

    # Use the id_token (JWT) as the gateway Bearer token; fall back to access_token.
    stored_token = id_token or access_token
    request.session["token"] = stored_token
    request.session["user"] = {
        "name": userinfo.get("name"),
        "email": userinfo.get("email"),
        "picture": userinfo.get("picture"),
    }
    return RedirectResponse(url=f"{FRONTEND_URL}/chat")


@app.get("/api/auth/me")
def me(request: Request):
    """Return the current user's identity for the frontend."""
    user = request.session.get("user")
    authenticated = "token" in request.session
    return {
        "authenticated": authenticated,
        "user": user or None,
        "gateway_url": GATEWAY_URL,
    }


@app.get("/api/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


# ── Gateway proxy routes ─────────────────────────────────────────────────────────
def _require_auth(request: Request):
    if "token" not in request.session:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    return None


@app.post("/api/gateway")
async def gateway_request(request: Request):
    """Proxy a raw JSON-RPC body (e.g. tools/list) to the Agent Gateway."""
    guard = _require_auth(request)
    if guard:
        return guard

    body = await request.json()
    if not body:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    headers = {
        "Authorization": f"Bearer {request.session['token']}",
        "Content-Type": "application/json",
    }
    try:
        status_code, resp_body = await _proxy_gateway_request(headers, body, "Google")
        return {"status": status_code, "body": resp_body}
    except httpx.HTTPError as e:
        print(f"[Google] Request error: {e}")
        return JSONResponse({"error": str(e), "status": 0, "body": {}}, status_code=502)


@app.post("/api/gateway/chat")
async def gateway_chat_request(request: Request):
    """Proxy a chat message as an MCP tools/call to the Agent Gateway."""
    guard = _require_auth(request)
    if guard:
        return guard

    body = await request.json()
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "Missing chat message"}, status_code=400)

    headers = {
        "Authorization": f"Bearer {request.session['token']}",
        "Content-Type": "application/json",
    }
    try:
        status_code, resp_body = await _proxy_gateway_request(
            headers, _chat_tool_request_body(message), "Google chat"
        )
        return {"status": status_code, "body": resp_body}
    except httpx.HTTPError as e:
        print(f"[Google] Chat request error: {e}")
        return JSONResponse({"error": str(e), "status": 0, "body": {}}, status_code=502)


@app.get("/api/health")
def health():
    return {"ok": True, "gateway_configured": bool(GATEWAY_URL)}


# ── Single-origin: serve the built Astro frontend ────────────────────────────
# Mounted LAST so the /api/* routes above always win. Present only after the
# frontend has been built (`npm run build` → frontend/dist). In two-server dev
# mode the dist folder is absent and Astro serves the frontend on :5137 instead.
_DIST = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _DIST.is_dir():
    # html=True → "/" serves index.html, "/chat" serves chat/index.html, etc.
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    print(f"\n{'='*60}")
    print("  Agent Gateway Chat — FastAPI backend")
    print(f"  App:              http://localhost:{PORT}")
    print(
        f"  Serving frontend: {'yes (dist found)' if _DIST.is_dir() else 'no (run npm build for single-origin)'}")
    print(f"  Callback:         {REDIRECT_URI}")
    print(f"  Frontend origin:  {FRONTEND_URL}")
    print(f"  Backend URL:      {BACKEND_URL or '(not set)'}")
    print(f"  Cookie:           domain={COOKIE_DOMAIN or '(host-only)'} "
          f"samesite={COOKIE_SAMESITE} secure={COOKIE_SECURE}")
    print(f"  Gateway (Google): {GATEWAY_URL or '(not set)'}")
    print(f"{'='*60}\n")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
