"""
Agent Gateway Chat — FastAPI backend (API only)

Caller context:        Google OAuth (user identity → verified by Trust Gateway)
Credential delegation: Auth0 OAuth (handled by Trust Gateway, on-demand consent)

This backend exposes a small JSON API consumed by the Astro + Alpine.js frontend.
It handles the Google OAuth login flow, keeps the user's Google id_token in a
signed session cookie, and proxies MCP requests to the Affinidi Trust Gateway.

The Trust Gateway is responsible for verifying the Google JWT (caller context)
and for delegating Auth0 credentials to the upstream MCP server on demand. When
the gateway needs consent it returns a `consent_required` payload containing an
`authorization_url`; the frontend renders that so the user can authorise.

Run:
    uvicorn main:app --reload --port 8000

Env vars (see .env.example):
    GOOGLE_CLIENT_ID       Google OAuth client ID
    GOOGLE_CLIENT_SECRET   Google OAuth client secret
    REDIRECT_URI           OAuth callback (default http://localhost:8000/api/auth/callback)
    GATEWAY_URL            Affinidi Trust Gateway MCP surface endpoint
    FRONTEND_URL           Astro frontend origin (default http://localhost:4321)
    SESSION_SECRET         Session cookie signing secret
    PORT                   Backend port (default 8000)
"""

import os
import time
import secrets

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
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
PORT = int(os.environ.get("PORT", 8000))
REDIRECT_URI = os.environ.get(
    "REDIRECT_URI", f"http://localhost:{PORT}/api/auth/callback"
)
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:4321")
SESSION_SECRET = os.environ.get("SESSION_SECRET", secrets.token_hex(32))

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

CHAT_TOOL_NAME = "chat"
AGENT_NAME = "chat-client"

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="Agent Gateway Chat API", version="1.0.0")

# Session cookie. same_site="lax" is sufficient because the Astro frontend
# (localhost:4321) and this backend (localhost:8000) share the same site
# (localhost); ports do not affect the cookie's site.
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False,  # set True behind HTTPS in production
)

# CORS so the Astro frontend can call this API with credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:4321", "http://localhost:8000"],
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
    """Forward a JSON-RPC body to the Trust Gateway and return (status, json)."""
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
    request.session["guest"] = False
    request.session["user"] = {
        "name": userinfo.get("name"),
        "email": userinfo.get("email"),
        "picture": userinfo.get("picture"),
    }
    return RedirectResponse(url=f"{FRONTEND_URL}/chat")


@app.get("/api/auth/guest")
def guest_login(request: Request):
    """Continue as guest — no gateway token; protected calls will 401."""
    request.session.clear()
    request.session["guest"] = True
    request.session["user"] = {
        "name": "Guest User",
        "email": "Not signed in",
        "picture": "",
    }
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request):
    """Return the current user's identity for the frontend."""
    user = request.session.get("user")
    authenticated = "token" in request.session
    return {
        "authenticated": authenticated,
        "guest": bool(request.session.get("guest")),
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
        if request.session.get("guest"):
            return JSONResponse(
                {"error": "401 Unauthorized: This gateway is protected with Google login. "
                          "Sign in with Google to continue."},
                status_code=401,
            )
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    return None


@app.post("/api/gateway")
async def gateway_request(request: Request):
    """Proxy a raw JSON-RPC body (e.g. tools/list) to the Trust Gateway."""
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
    """Proxy a chat message as an MCP tools/call to the Trust Gateway."""
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


if __name__ == "__main__":
    import uvicorn
    print(f"\n{'='*60}")
    print("  Agent Gateway Chat — FastAPI backend")
    print(f"  API:              http://localhost:{PORT}")
    print(f"  Callback:         {REDIRECT_URI}")
    print(f"  Frontend:         {FRONTEND_URL}")
    print(f"  Gateway (Google): {GATEWAY_URL or '(not set)'}")
    print(f"{'='*60}\n")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
