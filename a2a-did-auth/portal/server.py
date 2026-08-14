#!/usr/bin/env python3
"""
DID Auth Portal Backend

A small FastAPI app that lets a user walk through, one explicit step at a
time, three demo flows:

  1. Direct to the Echo Agent - no gateway, no auth.
  2. Through an Agent Gateway surface - no DID Auth configured yet.
  3. Through an Agent Gateway surface with DID Auth: challenge -> sign ->
     authenticate -> session-token-bearing A2A message.

Every step returns the exact request that was sent and the raw response, so
the UI can show what happened instead of hiding it behind one big button.

The managed agent (a2a-did-auth/agent.py) is never touched - all of the
DID Auth logic lives here, on the caller side. A did:key identity is
loaded or created automatically when the server starts.
"""

import os
from pathlib import Path
from typing import Optional
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from identity import CallerIdentity

load_dotenv(Path(__file__).parent.parent / ".env")

AGENT_URL = os.environ.get("AGENT_URL", "http://localhost:8001").rstrip("/")
GATEWAY_AGENT_URL = os.environ.get("GATEWAY_AGENT_URL", "").rstrip("/")
IDENTITY_FILE = Path(__file__).parent / "caller_identity.json"

app = FastAPI(title="A2A DID Auth Portal")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Ensure caller identity exists as soon as the server starts.
identity: Optional[CallerIdentity] = CallerIdentity.load_or_create(
    IDENTITY_FILE)


def _require_identity() -> CallerIdentity:
    if identity is None:
        raise HTTPException(
            400, "No DID yet. Create one first (POST /api/identity/create).")
    return identity


# In-memory session state (single demo caller, single active session)
class SessionState:
    surface_url: Optional[str] = None
    session_token: Optional[str] = None
    expires_at: Optional[str] = None
    expires_in: Optional[int] = None


session = SessionState()


class ChallengeRequest(BaseModel):
    surface_url: str


class SignRequest(BaseModel):
    challenge: str
    audience: Optional[str] = None


class AuthenticateRequest(BaseModel):
    surface_url: str
    challenge_response: str


class SendRequest(BaseModel):
    target_url: str
    message: str
    use_session: bool = False


def _http_client() -> httpx.Client:
    # verify=False mirrors the -k used in the DID Auth curl examples (self-signed gateway certs)
    return httpx.Client(timeout=15.0, verify=False)


def _a2a_body(message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "method": "message/send",
        "id": str(uuid4()),
        "params": {
            "message": {
                "role": "user",
                "messageId": f"msg-{uuid4().hex}",
                "parts": [{"kind": "text", "text": message}],
            }
        },
    }


def _safe_json(resp: httpx.Response):
    try:
        return resp.json()
    except ValueError:
        return resp.text


def _extract_reply(result) -> Optional[str]:
    if not isinstance(result, dict):
        return None
    try:
        parts = result["result"]["status"]["message"]["parts"]
        return " ".join(p.get("text", "") for p in parts if p.get("kind") == "text")
    except (KeyError, TypeError):
        return None


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/agent-card")
def get_agent_card():
    with _http_client() as client:
        try:
            resp = client.get(f"{AGENT_URL}/.well-known/agent-card.json")
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"Failed to reach {AGENT_URL}: {exc}")
    if resp.status_code != 200:
        raise HTTPException(
            resp.status_code, f"Agent card fetch failed: {resp.text}")
    return resp.json()


@app.get("/api/identity")
def get_identity():
    if identity is None:
        return {"did": None, "kid": None}
    return {"did": identity.did, "kid": identity.kid}


@app.post("/api/identity/create")
def create_identity():
    global identity
    created = identity is None
    if identity is None:
        identity = CallerIdentity.load_or_create(IDENTITY_FILE)
    return {"did": identity.did, "kid": identity.kid, "created": created}


@app.post("/api/identity/regenerate")
def regenerate_identity():
    global identity
    if IDENTITY_FILE.exists():
        IDENTITY_FILE.unlink()
    identity = CallerIdentity.load_or_create(IDENTITY_FILE)
    # A new DID invalidates any session established under the old one.
    session.surface_url = None
    session.session_token = None
    session.expires_at = None
    session.expires_in = None
    return {"did": identity.did, "kid": identity.kid}


@app.get("/api/status")
def get_status():
    return {
        "has_identity": identity is not None,
        "agent_url": AGENT_URL,
        "gateway_agent_url": GATEWAY_AGENT_URL,
        "authenticated": bool(session.session_token),
        "session_token": session.session_token,
        "surface_url": session.surface_url,
        "expires_at": session.expires_at,
        "expires_in": session.expires_in,
    }


@app.post("/api/logout")
def logout():
    session.surface_url = None
    session.session_token = None
    session.expires_at = None
    session.expires_in = None
    return {"authenticated": False}


@app.post("/api/flow/challenge")
def flow_challenge(req: ChallengeRequest):
    ident = _require_identity()
    surface_url = req.surface_url.rstrip("/")
    url = f"{surface_url}/authenticate/challenge"
    request_body = {"did": ident.did}

    with _http_client() as client:
        try:
            resp = client.post(url, json=request_body)
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"Failed to reach surface: {exc}")

    return {
        "request": {"method": "POST", "url": url, "body": request_body},
        "response": {"status_code": resp.status_code, "body": _safe_json(resp)},
    }


@app.post("/api/flow/sign")
def flow_sign(req: SignRequest):
    ident = _require_identity()
    jws, payload = ident.sign_challenge(req.challenge, aud=req.audience)
    return {
        "note": "Computed locally - no network call. The private key signs the challenge.",
        "header": {"alg": "EdDSA", "kid": ident.kid},
        "payload": payload,
        "jws": jws,
    }


@app.post("/api/flow/authenticate")
def flow_authenticate(req: AuthenticateRequest):
    ident = _require_identity()
    surface_url = req.surface_url.rstrip("/")
    url = f"{surface_url}/authenticate"
    request_body = {"did": ident.did,
                    "challenge_response": req.challenge_response}

    with _http_client() as client:
        try:
            resp = client.post(url, json=request_body)
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"Failed to reach surface: {exc}")

    response_body = _safe_json(resp)
    if resp.status_code == 200 and isinstance(response_body, dict) and "session_id" in response_body:
        session.surface_url = surface_url
        session.session_token = response_body["session_id"]
        session.expires_at = response_body.get("expires_at")
        session.expires_in = response_body.get("expires_in")

    return {
        "request": {"method": "POST", "url": url, "body": request_body},
        "response": {"status_code": resp.status_code, "body": response_body},
        "session_established": bool(session.session_token),
    }


@app.post("/api/flow/send")
def flow_send(req: SendRequest):
    target_url = req.target_url.rstrip("/")
    body = _a2a_body(req.message)
    headers = {"Content-Type": "application/json"}

    # If asked to use the session but none exists, send anyway with no token so the
    # caller sees the gateway's real rejection (e.g. 401 session token not found).
    if req.use_session and session.session_token:
        headers["Authorization"] = f"{session.session_token}"

    with _http_client() as client:
        try:
            resp = client.post(target_url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"Failed to reach {target_url}: {exc}")

    if resp.status_code == 401 and req.use_session:
        session.session_token = None

    response_body = _safe_json(resp)

    return {
        "request": {
            "method": "POST",
            "url": target_url,
            "headers": {k: v for k, v in headers.items() if k != "Content-Type"},
            "body": body,
        },
        "response": {"status_code": resp.status_code, "body": response_body},
        "reply": _extract_reply(response_body),
    }


if __name__ == "__main__":
    import uvicorn
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    uvicorn.run(app, host="0.0.0.0", port=port)
