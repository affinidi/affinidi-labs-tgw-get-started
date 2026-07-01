"""
Google OAuth + Agent Gateway Chat UI
Run: python oauth_chat_app.py
Env vars:
  GOOGLE_CLIENT_ID      - Google OAuth client ID
  GOOGLE_CLIENT_SECRET  - Google OAuth client secret
  REDIRECT_URI          - OAuth redirect URI (for example: http://localhost:8081/callback)
  GATEWAY_URL           - Agent Gateway endpoint
  PORT                  - Local port (default 8081)
  FLASK_SECRET_KEY      - Session secret (auto-generated if not set)
"""

import os
import json
import secrets
import time
import urllib.parse
import requests
from flask import Flask, redirect, request, session, jsonify, render_template_string

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

# ── Server-side OAuth state store (avoids session-cookie domain issues on OAuth redirects) ──
# Maps state_token -> expiry_timestamp
_OAUTH_STATE_TTL = 300  # 5 minutes
_oauth_states: dict[str, float] = {}


def _put_state(state: str) -> None:
    """Register a new OAuth state token."""
    # Purge expired entries
    now = time.time()
    expired = [k for k, exp in _oauth_states.items() if exp < now]
    for k in expired:
        _oauth_states.pop(k, None)
    _oauth_states[state] = now + _OAUTH_STATE_TTL


def _pop_state(state: str) -> bool:
    """Validate and consume an OAuth state token. Returns True if valid."""
    if not state:
        return False
    exp = _oauth_states.pop(state, None)
    return exp is not None and exp >= time.time()


# ── Configuration ──────────────────────────────────────────────────────────────
CLIENT_ID = os.environ.get(
    "GOOGLE_CLIENT_ID",
    ""
)
CLIENT_SECRET = os.environ.get(
    "GOOGLE_CLIENT_SECRET", "")
GATEWAY_URL = os.environ.get(
    "GATEWAY_URL",
    ""
)
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:8081/callback")
PORT = int(os.environ.get("PORT", 8081))

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

CHAT_TOOL_NAME = "chat"

# ── HTML Templates ─────────────────────────────────────────────────────────────

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Agent Gateway Login</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #0f0f11;
      color: #e2e8f0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .card {
      background: #1a1a2e;
      border: 1px solid #2d2d44;
      border-radius: 16px;
      padding: 40px 40px;
      width: 560px;
      text-align: center;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    }
    /* ── flow diagram ── */
    .flow {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0;
      margin: 28px 0 32px;
      flex-wrap: nowrap;
    }
    .flow-node {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      flex-shrink: 0;
    }
    .flow-box {
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 10px 14px;
      font-size: 11.5px;
      font-weight: 500;
      color: #e2e8f0;
      text-align: center;
      min-width: 90px;
      line-height: 1.4;
    }
    .flow-box.highlight {
      border-color: #4f46e5;
      background: #1e1b4b;
      color: #c7d2fe;
    }
    .flow-box.target {
      border-color: #0ea5e9;
      background: #0c2a3d;
      color: #7dd3fc;
    }
    .flow-icon { font-size: 18px; }
    .flow-label { font-size: 9.5px; color: #475569; text-transform: uppercase; letter-spacing: 0.6px; }
    .flow-arrow {
      font-size: 16px;
      color: #334155;
      margin: 0 4px;
      flex-shrink: 0;
      padding-bottom: 20px;
    }
    .flow-arrow.consent {
      color: #fbbf24;
    }
    .logo {
      width: 60px; height: 60px;
      background: linear-gradient(135deg, #667eea, #764ba2);
      border-radius: 16px;
      display: flex; align-items: center; justify-content: center;
      font-size: 28px;
      margin: 0 auto 24px;
    }
    h1 { font-size: 22px; font-weight: 600; margin-bottom: 8px; color: #f1f5f9; }
    .subtitle { font-size: 14px; color: #64748b; margin-bottom: 36px; line-height: 1.5; }
    .gateway-badge {
      background: #0f172a;
      border: 1px solid #1e3a5f;
      border-radius: 8px;
      padding: 10px 14px;
      font-size: 12px;
      color: #38bdf8;
      margin-bottom: 32px;
      word-break: break-all;
      text-align: left;
    }
    .gateway-badge span { color: #475569; display: block; margin-bottom: 4px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.8px; }
    .btn-google {
      display: flex; align-items: center; justify-content: center; gap: 12px;
      width: 100%;
      padding: 14px 20px;
      background: #fff;
      color: #1a1a1a;
      border: none; border-radius: 10px;
      font-size: 15px; font-weight: 500;
      cursor: pointer;
      transition: background 0.2s, transform 0.1s;
      text-decoration: none;
    }
    .btn-google:hover { background: #f1f5f9; transform: translateY(-1px); }
    .btn-google svg { flex-shrink: 0; }
    .btn-guest {
      display: block;
      width: 100%;
      margin-top: 10px;
      padding: 12px 20px;
      background: transparent;
      color: #94a3b8;
      border: 1px solid #334155;
      border-radius: 10px;
      font-size: 14px;
      font-weight: 500;
      text-decoration: none;
      transition: border-color 0.2s, color 0.2s, background 0.2s;
    }
    .btn-guest:hover {
      border-color: #475569;
      color: #e2e8f0;
      background: #111827;
    }
    .nav { display: flex; justify-content: center; gap: 6px; margin-bottom: 24px; }
    .nav a { font-size: 12px; color: #475569; text-decoration: none; padding: 5px 14px; border: 1px solid #1e1e30; border-radius: 20px; transition: all 0.2s; }
    .nav a:hover { color: #94a3b8; border-color: #334155; }
    .nav a.active { background: #1e1b4b; color: #818cf8; border-color: #3730a3; }
    .footer { margin-top: 24px; font-size: 12px; color: #334155; }
    @media (max-width: 600px) {
      body { align-items: flex-start; padding: 16px; }
      .card { width: 100%; padding: 24px 18px; border-radius: 12px; }
      h1 { font-size: 18px; }
      .subtitle { font-size: 13px; margin-bottom: 24px; }
      .flow { gap: 0; margin: 16px 0 20px; }
      .flow-box { min-width: 64px; font-size: 10px; padding: 7px 8px; }
      .flow-icon { font-size: 14px; }
      .flow-label { font-size: 8px; }
      .flow-arrow { font-size: 12px; margin: 0 2px; }
      .gateway-badge { font-size: 11px; margin-bottom: 20px; }
      .btn-google { font-size: 14px; padding: 12px 16px; }
      .logo { width: 48px; height: 48px; font-size: 22px; margin-bottom: 16px; }
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="nav">
      <a href="/" class="active">🔵 Google Flow</a>
    </div>
    <div class="logo">⚡</div>
    <h1>MCP via Agent Gateway</h1>
    <p class="subtitle">The Agent Gateway is protected with <strong>Google OAuth</strong>.<br>Upstream OAuth consent is handled by the gateway on your behalf.</p>

    <!-- Flow diagram -->
    <div class="flow">
      <div class="flow-node">
        <div class="flow-icon">👤</div>
        <div class="flow-box highlight">You<br><span style="font-size:10px;color:#818cf8">Google Login</span></div>
        <div class="flow-label">Google OAuth ★</div>
      </div>
      <div class="flow-arrow">&rarr;</div>
      <div class="flow-node">
        <div class="flow-icon">⚡</div>
        <div class="flow-box">Agent<br>Gateway</div>
        <div class="flow-label">Verifies Google token</div>
      </div>
      <div class="flow-arrow consent">&rarr;</div>
      <div class="flow-node">
        <div class="flow-icon">🔐</div>
        <div class="flow-box" style="border-color:#fbbf24;background:#2d1a00;color:#fde68a">Delegated<br>OAuth</div>
        <div class="flow-label">Upstream OAuth ★</div>
      </div>
      <div class="flow-arrow">&rarr;</div>
      <div class="flow-node">
        <div class="flow-icon">🔍</div>
        <div class="flow-box target">Target<br>MCP Server</div>
        <div class="flow-label">Protected upstream</div>
      </div>
    </div>

    <div class="gateway-badge">
      <span>Agent Gateway URL</span>
      {{ gateway_url }}
    </div>
    <a href="/login" class="btn-google">
      <svg width="20" height="20" viewBox="0 0 48 48">
        <path fill="#EA4335" d="M24 9.5c3.14 0 5.95 1.08 8.17 2.85l6.09-6.09C34.46 3.19 29.5 1 24 1 14.82 1 6.98 6.48 3.25 14.33l7.1 5.52C12.15 13.42 17.58 9.5 24 9.5z"/>
        <path fill="#4285F4" d="M46.5 24.5c0-1.57-.14-3.1-.4-4.58H24v8.67h12.68c-.55 2.93-2.2 5.41-4.68 7.07l7.24 5.62C43.47 37.24 46.5 31.32 46.5 24.5z"/>
        <path fill="#FBBC05" d="M10.35 28.14A14.54 14.54 0 0 1 9.5 24c0-1.44.25-2.84.85-4.14l-7.1-5.52A23.94 23.94 0 0 0 .5 24c0 3.87.92 7.53 2.55 10.77l7.3-6.63z"/>
        <path fill="#34A853" d="M24 47c5.5 0 10.12-1.82 13.49-4.94l-7.24-5.62c-1.87 1.26-4.27 2.01-6.25 2.01-6.42 0-11.85-3.92-13.65-9.36l-7.3 6.63C6.98 41.52 14.82 47 24 47z"/>
      </svg>
      Sign in with Google
    </a>
    <a href="/guest-login" class="btn-guest">Continue as Guest</a>
    <p class="footer">Signing in with Google grants access to the Agent Gateway.</p>
  </div>
</body>
</html>"""

CHAT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Agent Gateway Chat</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #0f0f11;
      color: #e2e8f0;
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    /* ── Header ──────────────────────────────────────────── */
    header {
      display: flex; align-items: center; gap: 12px;
      padding: 12px 20px;
      background: #13131f;
      border-bottom: 1px solid #1e1e30;
      flex-shrink: 0;
    }
    .avatar {
      width: 38px; height: 38px;
      border-radius: 50%;
      border: 2px solid #4f46e5;
    }
    .user-info { flex: 1; }
    .user-name { font-size: 14px; font-weight: 600; color: #f1f5f9; }
    .user-email { font-size: 12px; color: #64748b; }
    .gateway-pill {
      background: #0f172a;
      border: 1px solid #1e3a5f;
      border-radius: 20px;
      padding: 5px 12px;
      font-size: 11px;
      color: #38bdf8;
      max-width: 320px;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .flow-nav { display: flex; gap: 6px; }
    .flow-nav-link { font-size: 12px; color: #475569; text-decoration: none; padding: 5px 12px; border: 1px solid #1e1e30; border-radius: 20px; white-space: nowrap; transition: all 0.2s; }
    .flow-nav-link:hover { color: #e2e8f0; border-color: #334155; }
    .flow-nav-link.active { background: #1e1a3d; color: #818cf8; border-color: #3730a3; }
    .btn-logout {
      padding: 6px 14px;
      background: transparent;
      border: 1px solid #334155;
      border-radius: 8px;
      color: #94a3b8;
      font-size: 13px;
      cursor: pointer;
      text-decoration: none;
      transition: border-color 0.2s, color 0.2s;
    }
    .btn-logout:hover { border-color: #ef4444; color: #ef4444; }

    /* ── Chat area ───────────────────────────────────────── */
    .chat-wrapper {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      scroll-behavior: smooth;
    }
    .chat-wrapper::-webkit-scrollbar { width: 6px; }
    .chat-wrapper::-webkit-scrollbar-track { background: transparent; }
    .chat-wrapper::-webkit-scrollbar-thumb { background: #2d2d44; border-radius: 3px; }

    .msg { display: flex; gap: 10px; max-width: 90%; }
    .msg.user { align-self: flex-end; flex-direction: row-reverse; }
    .msg.system { align-self: center; max-width: 70%; }

    .msg-icon {
      width: 32px; height: 32px; border-radius: 8px;
      flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
      font-size: 16px;
    }
    .msg.user .msg-icon { background: #4f46e5; }
    .msg.assistant .msg-icon { background: #1e293b; border: 1px solid #334155; }
    .msg.system .msg-icon { display: none; }

    .msg-bubble {
      border-radius: 12px;
      padding: 12px 16px;
      font-size: 13px;
      line-height: 1.6;
    }
    .msg.user .msg-bubble {
      background: #4f46e5;
      color: #fff;
      border-bottom-right-radius: 4px;
    }
    .msg.assistant .msg-bubble {
      background: #1a1a2e;
      border: 1px solid #2d2d44;
      border-bottom-left-radius: 4px;
    }
    .msg.system .msg-bubble {
      background: #1e1e30;
      border: 1px dashed #334155;
      color: #64748b;
      font-size: 12px;
      text-align: center;
      border-radius: 8px;
    }

    .msg-label {
      font-size: 10px;
      color: #475569;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      margin-bottom: 4px;
    }
    .msg.user .msg-label { text-align: right; }

    /* JSON prettifier */
    .json-block {
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 8px;
      padding: 12px;
      font-family: 'SF Mono', 'Fira Code', monospace;
      font-size: 11.5px;
      line-height: 1.7;
      overflow-x: auto;
      white-space: pre;
      color: #94a3b8;
      margin-top: 8px;
    }
    .json-block .key { color: #7dd3fc; }
    .json-block .string { color: #86efac; }
    .json-block .number { color: #fbbf24; }
    .json-block .bool { color: #f472b6; }
    .json-block .null { color: #94a3b8; }
    .response-card {
      margin-top: 10px;
      background: #111827;
      border: 1px solid #243041;
      border-radius: 12px;
      padding: 14px 16px;
    }
    .response-title {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: #7dd3fc;
      margin-bottom: 10px;
    }
    .response-text {
      color: #e2e8f0;
      font-size: 13px;
      line-height: 1.7;
    }
    .response-text p + p { margin-top: 12px; }
    .response-text a { color: #7dd3fc; text-decoration: none; }
    .response-text a:hover { text-decoration: underline; }
    .response-text strong { color: #f8fafc; }
    .response-text code {
      background: #0f172a;
      border: 1px solid #223048;
      border-radius: 6px;
      padding: 1px 6px;
      font-size: 12px;
      color: #cbd5e1;
    }
    .response-divider {
      border: 0;
      border-top: 1px solid #243041;
      margin: 12px 0;
    }
    .meta-list {
      display: grid;
      gap: 8px;
      margin-top: 8px;
    }
    .meta-row {
      display: grid;
      grid-template-columns: 120px 1fr;
      gap: 10px;
      align-items: start;
      font-size: 12px;
    }
    .meta-key { color: #64748b; }
    .meta-value {
      color: #cbd5e1;
      word-break: break-word;
      font-family: 'SF Mono', 'Fira Code', monospace;
      font-size: 11.5px;
    }
    .tools-list {
      display: grid;
      gap: 10px;
      margin-top: 8px;
    }
    .tool-card {
      background: #0f172a;
      border: 1px solid #223048;
      border-radius: 10px;
      padding: 12px;
    }
    .tool-name {
      font-weight: 700;
      color: #f8fafc;
      margin-bottom: 4px;
    }
    .tool-description {
      font-size: 12px;
      line-height: 1.6;
      color: #cbd5e1;
    }
    .raw-response {
      margin-top: 10px;
      border: 1px solid #243041;
      border-radius: 10px;
      background: #0b1220;
      overflow: hidden;
    }
    .raw-response summary {
      cursor: pointer;
      list-style: none;
      padding: 10px 12px;
      color: #94a3b8;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.7px;
    }
    .raw-response summary::-webkit-details-marker { display: none; }
    .raw-response summary::after {
      content: 'Show';
      float: right;
      color: #64748b;
      font-weight: 500;
    }
    .raw-response[open] summary::after { content: 'Hide'; }
    .raw-response .json-block {
      margin-top: 0;
      border: 0;
      border-top: 1px solid #243041;
      border-radius: 0;
      background: #0f172a;
    }

    /* Auth URL card */
    .auth-card {
      margin-top: 10px;
      background: #1a2744;
      border: 1px solid #1e3a5f;
      border-radius: 10px;
      padding: 14px 16px;
    }
    .auth-card .auth-title {
      font-size: 12px;
      font-weight: 600;
      color: #fbbf24;
      margin-bottom: 8px;
      display: flex; align-items: center; gap: 6px;
    }
    .auth-card .auth-url {
      font-size: 11px;
      color: #38bdf8;
      word-break: break-all;
      margin-bottom: 10px;
    }
    .btn-open-auth {
      display: inline-block;
      padding: 7px 16px;
      background: #1d4ed8;
      color: #fff;
      border: none;
      border-radius: 7px;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      text-decoration: none;
      transition: background 0.2s;
    }
    .btn-open-auth:hover { background: #2563eb; }

    /* Status badge */
    .status-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 600;
      margin-bottom: 6px;
    }
    .status-badge.ok { background: #14532d; color: #86efac; }
    .status-badge.err { background: #4c1d1d; color: #fca5a5; }
    .status-badge.warn { background: #451a03; color: #fbbf24; }

    /* Loading dots */
    .loading { display: flex; gap: 4px; align-items: center; padding: 4px 0; }
    .loading span {
      width: 7px; height: 7px; border-radius: 50%;
      background: #4f46e5;
      animation: bounce 1.2s infinite;
    }
    .loading span:nth-child(2) { animation-delay: 0.2s; }
    .loading span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes bounce {
      0%, 80%, 100% { transform: scale(0.7); opacity: 0.5; }
      40% { transform: scale(1); opacity: 1; }
    }

    /* ── Input area ──────────────────────────────────────── */
    .input-area {
      padding: 12px 20px 16px;
      background: #13131f;
      border-top: 1px solid #1e1e30;
      flex-shrink: 0;
    }

    .quick-actions {
      display: flex; gap: 8px;
      margin-bottom: 10px;
      flex-wrap: wrap;
    }
    .btn-action {
      padding: 6px 14px;
      background: #1e1e30;
      border: 1px solid #334155;
      border-radius: 20px;
      color: #94a3b8;
      font-size: 12px;
      cursor: pointer;
      transition: background 0.2s, color 0.2s, border-color 0.2s;
    }
    .btn-action:hover { background: #2d2d50; color: #e2e8f0; border-color: #4f46e5; }
    .btn-action.active { background: #312e81; color: #c7d2fe; border-color: #4f46e5; }

    .input-row { display: flex; gap: 10px; align-items: flex-end; }
    textarea#msgInput {
      flex: 1;
      background: #1a1a2e;
      border: 1px solid #2d2d44;
      border-radius: 10px;
      color: #e2e8f0;
      font-size: 13px;
      padding: 10px 14px;
      resize: none;
      min-height: 44px;
      max-height: 140px;
      line-height: 1.5;
      font-family: inherit;
      transition: border-color 0.2s;
      outline: none;
    }
    textarea#msgInput:focus { border-color: #4f46e5; }
    textarea#msgInput::placeholder { color: #334155; }

    .btn-send {
      padding: 10px 20px;
      background: #4f46e5;
      border: none;
      border-radius: 10px;
      color: #fff;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      height: 44px;
      transition: background 0.2s, transform 0.1s;
      flex-shrink: 0;
    }
    .btn-send:hover { background: #4338ca; }
    .btn-send:active { transform: scale(0.97); }
    .btn-send:disabled { background: #312e81; opacity: 0.5; cursor: not-allowed; }

    /* JSON editor modal */
    .modal-overlay {
      display: none;
      position: fixed; inset: 0;
      background: rgba(0,0,0,0.7);
      z-index: 100;
      align-items: center; justify-content: center;
    }
    .modal-overlay.open { display: flex; }
    .modal {
      background: #1a1a2e;
      border: 1px solid #2d2d44;
      border-radius: 16px;
      padding: 24px;
      width: 560px;
      max-width: 90vw;
    }
    .modal h3 { font-size: 16px; margin-bottom: 14px; color: #f1f5f9; }
    .modal textarea {
      width: 100%;
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 8px;
      color: #94a3b8;
      font-family: 'SF Mono', 'Fira Code', monospace;
      font-size: 12px;
      padding: 12px;
      height: 200px;
      resize: vertical;
      outline: none;
    }
    .modal-actions { display: flex; gap: 8px; margin-top: 12px; justify-content: flex-end; }
    .btn-modal-cancel { padding: 8px 16px; background: transparent; border: 1px solid #334155; border-radius: 8px; color: #94a3b8; cursor: pointer; font-size: 13px; }
    .btn-modal-send { padding: 8px 16px; background: #4f46e5; border: none; border-radius: 8px; color: #fff; cursor: pointer; font-size: 13px; }
    @media (max-width: 600px) {
      header { padding: 8px 12px; gap: 8px; }
      .avatar { width: 30px; height: 30px; }
      .user-name { font-size: 13px; }
      .user-email { display: none; }
      .gateway-pill { display: none; }
      .btn-logout { padding: 5px 10px; font-size: 12px; }
      .chat-wrapper { padding: 12px; gap: 12px; }
      .msg { max-width: 100%; }
      .json-block { font-size: 10.5px; }
      .input-area { padding: 8px 12px 12px; }
      .quick-actions { gap: 6px; }
      .btn-action { padding: 5px 10px; font-size: 11px; }
      .btn-send { padding: 8px 14px; font-size: 13px; }
      .modal { width: 95vw; padding: 16px; }
      .fd-node { display: none; }
      .flow-diagram { display: none; }
    }

    /* welcome message */
    .welcome {
      text-align: center; padding: 32px 20px 20px; color: #334155;
    }
    .welcome h2 { font-size: 18px; color: #475569; margin-bottom: 6px; }
    .welcome p { font-size: 12.5px; line-height: 1.6; }
    /* ── inline flow diagram (chat) ── */
    .flow-diagram {
      display: flex;
      align-items: flex-start;
      justify-content: center;
      gap: 0;
      margin: 20px auto 8px;
      max-width: 680px;
      flex-wrap: nowrap;
    }
    .fd-node {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 5px;
      min-width: 100px;
    }
    .fd-icon { font-size: 20px; }
    .fd-box {
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 8px 10px;
      font-size: 11px;
      font-weight: 500;
      color: #cbd5e1;
      text-align: center;
      line-height: 1.45;
      width: 96px;
    }
    .fd-box.you   { border-color:#4f46e5; background:#1e1b4b; color:#c7d2fe; }
    .fd-box.gw    { border-color:#334155; background:#0f172a; color:#94a3b8; }
    .fd-box.gloauth { border-color:#fbbf24; background:#2d1a00; color:#fde68a; }
    .fd-box.glean { border-color:#0ea5e9; background:#0c2a3d; color:#7dd3fc; }
    .fd-label { font-size: 9px; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }
    .fd-desc  { font-size: 10px; color: #334155; max-width: 96px; line-height: 1.3; }
    .fd-arrow {
      font-size: 18px;
      color: #2d2d44;
      padding: 0 2px;
      margin-top: 24px;
      flex-shrink: 0;
    }
    .fd-arrow.warn { color: #92400e; }

    /* ── caller context card ── */
    .ctx-card { margin-top: 10px; background: #0d1117; border: 1px solid #1e293b; border-radius: 10px; overflow: hidden; }
    .ctx-header {
      display: flex; align-items: center; gap: 8px;
      padding: 10px 14px; background: #111827; border-bottom: 1px solid #1e293b;
      font-size: 12px; font-weight: 600; color: #94a3b8;
      cursor: pointer; user-select: none;
    }
    .ctx-header .ctx-badge { margin-left: auto; font-size: 10px; background: #1e3a5f; color: #38bdf8; padding: 2px 8px; border-radius: 10px; }
    .ctx-body { padding: 12px 14px; display: flex; flex-direction: column; gap: 10px; }
    .ctx-section-title { font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.7px; color: #475569; margin-bottom: 5px; }
    .ctx-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; }
    .ctx-field { background: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 7px 10px; }
    .ctx-field .lbl { font-size: 9.5px; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; }
    .ctx-field .val { font-size: 11.5px; color: #e2e8f0; margin-top: 2px; word-break: break-all; }
    .ctx-field.full { grid-column: 1 / -1; }
    .ctx-chip { display: inline-flex; align-items: center; gap: 5px; background: #14532d; border: 1px solid #166534; border-radius: 6px; padding: 5px 10px; font-size: 11px; color: #86efac; }
    .ctx-chip.yellow { background: #2d1a00; border-color: #92400e; color: #fde68a; }

    /* ── caller context card ── */
    .ctx-card {
      margin-top: 10px;
      background: #0d1117;
      border: 1px solid #1e293b;
      border-radius: 10px;
      overflow: hidden;
    }
    .ctx-header {
      display: flex; align-items: center; gap: 8px;
      padding: 10px 14px;
      background: #111827;
      border-bottom: 1px solid #1e293b;
      font-size: 12px; font-weight: 600; color: #94a3b8;
      cursor: pointer;
      user-select: none;
    }
    .ctx-header .ctx-badge {
      margin-left: auto;
      font-size: 10px;
      background: #1e3a5f;
      color: #38bdf8;
      padding: 2px 8px;
      border-radius: 10px;
    }
    .ctx-body { padding: 12px 14px; display: flex; flex-direction: column; gap: 10px; }
    .ctx-section-title {
      font-size: 9.5px;
      text-transform: uppercase;
      letter-spacing: 0.7px;
      color: #475569;
      margin-bottom: 5px;
    }
    .ctx-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 6px;
    }
    .ctx-field {
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 6px;
      padding: 7px 10px;
    }
    .ctx-field .lbl { font-size: 9.5px; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; }
    .ctx-field .val { font-size: 11.5px; color: #e2e8f0; margin-top: 2px; word-break: break-all; }
    .ctx-field.full { grid-column: 1 / -1; }
    .ctx-chip {
      display: inline-flex; align-items: center; gap: 5px;
      background: #14532d;
      border: 1px solid #166534;
      border-radius: 6px;
      padding: 5px 10px;
      font-size: 11px;
      color: #86efac;
    }
    .ctx-chip.blue {
      background: #1e3a5f; border-color: #1d4ed8; color: #93c5fd;
    }
    .ctx-chip.yellow {
      background: #2d1a00; border-color: #92400e; color: #fde68a;
    }
    .ctx-toggle { display: none; }
    .ctx-toggle:checked + .ctx-card .ctx-body { display: none; }
  </style>
</head>
<body>

<header>
  <img src="{{ user_picture }}" alt="avatar" class="avatar" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 40 40%22><rect width=%2240%22 height=%2240%22 fill=%22%234f46e5%22 rx=%2220%22/><text y=%2226%22 x=%2214%22 font-size=%2220%22 fill=%22white%22>U</text></svg>'">
  <div class="user-info">
    <div class="user-name">{{ user_name }}</div>
    <div class="user-email">{{ user_email }}</div>
  </div>
  <div class="gateway-pill" title="{{ gateway_url }}">🔗 Gateway Access Point URL: {{ gateway_url }}</div>
  <a href="/logout" class="btn-logout">Logout</a>
</header>

<div class="chat-wrapper" id="chatContainer">
  <div class="welcome">
    <h2>Gateway Chat</h2>
    {% if is_guest %}
    <p>You are in guest mode. Gateway actions will return 401 because this endpoint is protected with Google login. Click Logout and sign in with Google to continue.</p>
    {% else %}
    <p>You're authenticated with Google. Use the actions below to call the MCP server via the gateway.</p>
    {% endif %}

    <div class="flow-diagram">
      <div class="fd-node">
        <div class="fd-icon">👤</div>
        <div class="fd-box you">You<br><span style="font-size:9.5px">Google token</span></div>
        <div class="fd-label">Google OAuth ★</div>
        <div class="fd-desc">Gateway protected</div>
      </div>

      <div class="fd-arrow">→</div>

      <div class="fd-node">
        <div class="fd-icon">⚡</div>
        <div class="fd-box gw">Agent<br>Gateway</div>
        <div class="fd-label">Verifies Google token</div>
        <div class="fd-desc">Builds Caller Context VP</div>
      </div>

      <div class="fd-arrow warn">→</div>

      <div class="fd-node">
        <div class="fd-icon">🔐</div>
        <div class="fd-box gloauth">Delegated<br>OAuth</div>
        <div class="fd-label">Upstream OAuth ★</div>
        <div class="fd-desc">Gateway handles this — consent once</div>
      </div>

      <div class="fd-arrow">→</div>

      <div class="fd-node">
        <div class="fd-icon">🔄</div>
        <div class="fd-box gw">Gateway<br>Callback</div>
        <div class="fd-label">Auth code flow</div>
        <div class="fd-desc">Gateway stores delegated token</div>
      </div>

      <div class="fd-arrow">→</div>

      <div class="fd-node">
        <div class="fd-icon">🔍</div>
        <div class="fd-box glean">Target<br>MCP Server</div>
        <div class="fd-label">Protected upstream</div>
        <div class="fd-desc">Gateway calls with delegated token</div>
      </div>
    </div>
  </div>
</div>

<div class="input-area">
  <div class="quick-actions">
    <button class="btn-action" onclick="listTools()">📋 List Tools</button>
    <button class="btn-action" onclick="sendPrompt('What is Agent Gateway?')">What is Agent Gateway?</button>
    <button class="btn-action" onclick="sendPrompt('What are Agent Gateway capabilities?')">Agent Gateway Capabilities</button>
    <button class="btn-action" onclick="sendPrompt('What does the Gateway do?')">What the Gateway does</button>
    <button class="btn-action" onclick="sendPrompt('How does the Gateway evaluate every request?')">How Gateway evaluates requests</button>
    <button class="btn-action" onclick="sendPrompt('Summarize the core features of Agent Gateway')">Core Features</button>
  </div>
  <div class="input-row">
    <textarea id="msgInput" placeholder="Type a message for Chat..." rows="1"
      onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>
    <button class="btn-send" id="sendBtn" onclick="sendMessage()">Send ↑</button>
  </div>
</div>

<script>
const GATEWAY_URL = {{ gateway_url_json | safe }};
let requestId = 10;

// ── Helpers ────────────────────────────────────────────────────────────────

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 140) + 'px';
}

function scrollToBottom() {
  const c = document.getElementById('chatContainer');
  c.scrollTop = c.scrollHeight;
}

function addMessage(role, content) {
  const c = document.getElementById('chatContainer');
  const welcome = c.querySelector('.welcome');
  if (welcome) welcome.remove();

  const div = document.createElement('div');
  div.className = 'msg ' + role;

  const icons = { user: '👤', assistant: '⚡', system: '' };
  div.innerHTML = `
    <div class="msg-icon">${icons[role] || ''}</div>
    <div>
      <div class="msg-label">${role === 'user' ? 'You' : role === 'assistant' ? 'Gateway Chat' : ''}</div>
      <div class="msg-bubble" id="bubble-${Date.now()}">${content}</div>
    </div>`;
  c.appendChild(div);
  scrollToBottom();
  return div.querySelector('.msg-bubble');
}

function addLoading() {
  const bubble = addMessage('assistant', '<div class="loading"><span></span><span></span><span></span></div>');
  bubble._isLoading = true;
  return bubble;
}

// ── JSON syntax highlighter ────────────────────────────────────────────────

function highlightJson(obj) {
  const str = JSON.stringify(obj, null, 2);
  return str.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, match => {
    if (/^"/.test(match)) {
      if (/:$/.test(match)) return `<span class="key">${match}</span>`;
      return `<span class="string">${match}</span>`;
    }
    if (/true|false/.test(match)) return `<span class="bool">${match}</span>`;
    if (/null/.test(match)) return `<span class="null">${match}</span>`;
    return `<span class="number">${match}</span>`;
  });
}

function renderInlineMarkdown(text) {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
}

function renderRichText(text) {
  const blocks = text.split(/\\n\s*\\n/).map(part => part.trim()).filter(Boolean);
  return blocks.map(block => {
    if (block === '---') return '<hr class="response-divider">';
    return `<p>${renderInlineMarkdown(block).replace(/\\n/g, '<br>')}</p>`;
  }).join('');
}

function extractChatContent(body) {
  if (!body || !body.result || !Array.isArray(body.result.content)) return null;
  const textPart = body.result.content.find(item => item.type === 'text' && item.text);
  return textPart ? textPart.text : null;
}

function splitChatContent(rawText) {
  const marker = /\\n---\\nchatId:/;
  const match = rawText.match(marker);
  if (!match || match.index === undefined) {
    return { answer: rawText.trim(), metadata: '' };
  }

  return {
    answer: rawText.slice(0, match.index).trim(),
    metadata: rawText.slice(match.index + 5).trim()
  };
}

function parseMetadataLines(metadataText) {
  const lines = metadataText.split('\\n').map(line => line.trim()).filter(Boolean);
  const rows = [];
  for (const line of lines) {
    if (line === '-' || line === '---') continue;
    const parts = line.split(/:\s(.+)/);
    if (parts.length >= 3) {
      rows.push({ key: parts[0], value: parts[1] });
    } else {
      rows.push({ key: 'detail', value: line });
    }
  }
  return rows;
}

function renderMetadata(metadataText) {
  if (!metadataText) return '';
  const rows = parseMetadataLines(metadataText);
  if (!rows.length) return '';

  return `
    <details class="raw-response">
      <summary>Trace Metadata</summary>
      <div class="meta-list" style="padding:10px 12px">
        ${rows.map(row => `<div class="meta-row"><div class="meta-key">${escapeHtml(row.key)}</div><div class="meta-value">${escapeHtml(row.value)}</div></div>`).join('')}
      </div>
    </details>`;
}

function renderToolList(body) {
  const tools = body && body.result && Array.isArray(body.result.tools) ? body.result.tools : null;
  if (!tools || !tools.length) return '';

  return `
    <div class="response-card">
      <div class="response-title">Available Tools</div>
      <div class="tools-list">
        ${tools.map(tool => `
          <div class="tool-card">
            <div class="tool-name">${escapeHtml(tool.name || 'Unnamed tool')}</div>
            <div class="tool-description">${renderInlineMarkdown(tool.description || 'No description')}</div>
          </div>
        `).join('')}
      </div>
    </div>`;
}

function renderPrimaryResponse(body) {
  const chatText = extractChatContent(body);
  if (chatText) {
    const parts = splitChatContent(chatText);
    let html = `
      <div class="response-card">
        <div class="response-title">Gateway Chat Response</div>
        <div class="response-text">${renderRichText(parts.answer)}</div>
      </div>`;
    html += renderMetadata(parts.metadata);
    return html;
  }

  return renderToolList(body);
}

function renderRawResponse(body) {
  if (!body || Object.keys(body).length === 0) return '';
  return `<details class="raw-response"><summary>Raw MCP response</summary><div class="json-block">${highlightJson(body)}</div></details>`;
}

function renderRawRequest(body) {
  if (!body || Object.keys(body).length === 0) return '';
  return `<details class="raw-response"><summary>Raw MCP request</summary><div class="json-block">${highlightJson(body)}</div></details>`;
}

// ── Caller Context VP renderer ─────────────────────────────────────────────

function renderCallerContext(vp) {
  try {
    const vc = vp.verifiableCredential;
    if (!vc) return '';
    const wb = vc.credentialSubject && vc.credentialSubject.workloadBinding;
    if (!wb) return '';

    const user = wb.userIdentity || {};
    const agent = wb.agentIdentity || {};
    const intent = wb.intent || {};
    const delegations = wb.delegationAction || [];
    const traceId = wb.traceId || '';

    let html = `<div class="ctx-card">`;
    html += `<div class="ctx-header" onclick="const b=this.nextElementSibling;b.style.display=b.style.display==='none'?'':'none'">`;
    html += `📦 Gateway Caller Context`;
    html += `<span class="ctx-badge">Verifiable Presentation</span>`;
    html += `</div>`;
    html += `<div class="ctx-body">`;

    // User Identity
    html += `<div>`;
    html += `<div class="ctx-section-title">👤 User Identity <span style="color:#818cf8;font-size:9px">(Google OAuth — User Context)</span></div>`;
    html += `<div class="ctx-grid">`;
    html += `<div class="ctx-field"><div class="lbl">Name</div><div class="val">${escapeHtml(user.name || '—')}</div></div>`;
    html += `<div class="ctx-field"><div class="lbl">Email</div><div class="val">${escapeHtml(user.email || '—')}</div></div>`;
    html += `<div class="ctx-field"><div class="lbl">Subject (sub)</div><div class="val">${escapeHtml(user.sub || '—')}</div></div>`;
    html += `<div class="ctx-field"><div class="lbl">Issuer (iss)</div><div class="val">${escapeHtml(user.iss || '—')}</div></div>`;
    html += `</div></div>`;

    // Workload Binding
    html += `<div>`;
    html += `<div class="ctx-section-title">⚡ Workload Binding</div>`;
    html += `<div class="ctx-grid">`;
    html += `<div class="ctx-field"><div class="lbl">Agent Name</div><div class="val">${escapeHtml(agent.name || '—')}</div></div>`;
    html += `<div class="ctx-field"><div class="lbl">Trace ID</div><div class="val">${escapeHtml(traceId)}</div></div>`;
    html += `</div></div>`;

    // Intent
    if (intent.protocol) {
      html += `<div>`;
      html += `<div class="ctx-section-title">🎯 Intent</div>`;
      html += `<div class="ctx-grid">`;
      html += `<div class="ctx-field"><div class="lbl">Protocol</div><div class="val">${escapeHtml(intent.protocol)}</div></div>`;
      html += `<div class="ctx-field"><div class="lbl">Method</div><div class="val">${escapeHtml(intent.method || '—')}</div></div>`;
      if (intent.tool) html += `<div class="ctx-field full"><div class="lbl">Tool</div><div class="val">${escapeHtml(intent.tool)}</div></div>`;
      html += `</div></div>`;
    }

    // Credentials Delegation
    if (delegations.length > 0) {
      html += `<div>`;
      html += `<div class="ctx-section-title">🔐 Credentials Delegation <span style="color:#fbbf24;font-size:9px">(Upstream OAuth — Handled by Gateway)</span></div>`;
      html += `<div style="display:flex;flex-wrap:wrap;gap:6px">`;
      delegations.forEach(d => {
        const cls = d.outcome === 'token_injected' ? '' : 'yellow';
        html += `<div class="ctx-chip ${cls}">🔗 <strong>${escapeHtml(d.providerName || d.providerId)}</strong> &mdash; <span style="opacity:0.8">${escapeHtml(d.outcome)}</span></div>`;
      });
      html += `</div></div>`;
    }

    html += `</div></div>`;
    return html;
  } catch (e) {
    return '';
  }
}

// ── Response renderer ──────────────────────────────────────────────────────

function renderResponse(bubble, data, requestBody) {
  const status = data.status;
  const body = data.body;

  let html = '';

  // Status badge
  // Check for consent required
  if (body && body.consent_required && body.consent_required.length > 0) {
    const consent = body.consent_required[0];
    const authUrl = consent.authorization_url || '';
    html += `<div class="auth-card">
      <div class="auth-title">🔐 Additional Consent Required</div>
      <div class="auth-url">${escapeHtml(authUrl)}</div>
      <p style="font-size:11px;color:#94a3b8;margin-bottom:10px">The gateway needs your permission to access the upstream service on your behalf. Click below to authorise, then retry your request.</p>
      ${authUrl ? `<a href="${escapeHtml(authUrl)}" target="_blank" class="btn-open-auth">Authorise Access ↗</a>` : ''}
    </div>`;
  }

  // Caller context VP — extract from result if present
  let vpSource = null;
  if (body && body.result) {
    // may be nested inside result.content[].text as JSON string, or directly
    if (body.result.verifiableCredential) {
      vpSource = body.result;
    } else if (Array.isArray(body.result.content)) {
      for (const c of body.result.content) {
        if (c.type === 'text' && c.text) {
          try { const p = JSON.parse(c.text); if (p.verifiableCredential) { vpSource = p; break; } } catch(_) {}
        }
      }
    }
  }
  if (body && body.verifiableCredential) vpSource = body;
  if (vpSource) html += renderCallerContext(vpSource);

  const primaryResponse = renderPrimaryResponse(body);
  if (primaryResponse) {
    html += primaryResponse;
  }

  // Always show the outgoing MCP request in collapsed form.
  html += renderRawRequest(requestBody);

  if (body && Object.keys(body).length > 0) {
    html += renderRawResponse(body);
  } else if (data.error) {
    html += `<div class="json-block" style="color:#fca5a5">${escapeHtml(data.error)}</div>`;
  }

  bubble.innerHTML = html;
  scrollToBottom();
}

function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── API call ───────────────────────────────────────────────────────────────

async function callGateway(body, userLabel) {
  addMessage('user', escapeHtml(userLabel || JSON.stringify(body)));
  const loadingBubble = addLoading();
  document.getElementById('sendBtn').disabled = true;

  try {
    const resp = await fetch('/api/gateway', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await resp.json();
    renderResponse(loadingBubble, data, body);
  } catch (err) {
    loadingBubble.innerHTML = `<span style="color:#fca5a5">Error: ${escapeHtml(err.message)}</span>`;
  } finally {
    document.getElementById('sendBtn').disabled = false;
    scrollToBottom();
  }
}

function buildChatToolCall(message) {
  return {
    jsonrpc: '2.0',
    id: requestId++,
    method: 'tools/call',
    params: {
      _meta: { agentIdentity: { name: 'chat-client', version: '1.0.0' } },
      name: 'chat',
      arguments: { message }
    }
  };
}

async function callChatTool(message) {
  addMessage('user', escapeHtml(message));
  const loadingBubble = addLoading();
  document.getElementById('sendBtn').disabled = true;
  const requestBody = buildChatToolCall(message);

  try {
    const resp = await fetch('/api/gateway/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });
    const data = await resp.json();
    renderResponse(loadingBubble, data, requestBody);
  } catch (err) {
    loadingBubble.innerHTML = `<span style="color:#fca5a5">Error: ${escapeHtml(err.message)}</span>`;
  } finally {
    document.getElementById('sendBtn').disabled = false;
    scrollToBottom();
  }
}

// ── Quick actions ──────────────────────────────────────────────────────────

function sendPrompt(text) {
  document.getElementById('msgInput').value = text;
  sendMessage();
}

function listTools() {
  callGateway({
    jsonrpc: '2.0',
    id: requestId++,
    method: 'tools/list',
    params: { _meta: { agentIdentity: { name: 'chat-client', version: '1.0.0' } } }
  }, '📋 List Tools');
}

function sendMessage() {
  const input = document.getElementById('msgInput');
  const text = input.value.trim();
  if (!text) return;

  // Detect raw JSON-RPC
  if (text.startsWith('{')) {
    try {
      const parsed = JSON.parse(text);
      input.value = '';
      autoResize(input);
      callGateway(parsed, text);
      return;
    } catch (_) { /* not valid JSON, treat as query */ }
  }

  input.value = '';
  autoResize(input);
  callChatTool(text);
}
</script>
</body>
</html>"""

# ── Routes ─────────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    if "token" not in session and not session.get("guest"):
        return render_template_string(LOGIN_HTML, gateway_url=GATEWAY_URL)
    user = session.get("user", {})
    return render_template_string(
        CHAT_HTML,
        user_name=user.get("name", "User"),
        user_email=user.get("email", ""),
        user_picture=user.get("picture", ""),
        gateway_url=GATEWAY_URL,
        gateway_url_json=json.dumps(GATEWAY_URL),
        is_guest=bool(session.get("guest")),
    )


@app.route("/login")
def login():
    state = secrets.token_hex(16)
    _put_state(state)
    params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })
    return redirect(f"{GOOGLE_AUTH_URL}?{params}")


@app.route("/guest-login")
def guest_login():
    session.clear()
    session["guest"] = True
    session["user"] = {
        "name": "Guest User",
        "email": "Not signed in",
        "picture": "",
    }
    return redirect("/")


@app.route("/callback")
def callback():
    # CSRF check (server-side state store — works across ngrok domain redirects)
    if not _pop_state(request.args.get("state", "")):
        return "State mismatch – possible CSRF attack.", 400

    code = request.args.get("code")
    error = request.args.get("error")
    if error:
        return f"OAuth error: {error}", 400
    if not code:
        return "No authorization code received.", 400

    # Exchange code for tokens
    token_resp = requests.post(GOOGLE_TOKEN_URL, data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }, timeout=15)
    tokens = token_resp.json()

    if "error" in tokens:
        return f"Token exchange failed: {tokens.get('error_description', tokens['error'])}", 400

    access_token = tokens.get("access_token")
    id_token = tokens.get("id_token")

    # Fetch user info
    userinfo_resp = requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    userinfo = userinfo_resp.json()

    # Store in session – use id_token (JWT) as the Bearer token, fall back to access_token
    stored_token = id_token or access_token
    print(f"[Google] Token response keys: {list(tokens.keys())}")
    print(f"[Google] Stored token (first 60 chars): {stored_token[:60]}...")
    session["token"] = stored_token
    session["access_token"] = access_token
    session["user"] = {
        "name": userinfo.get("name"),
        "email": userinfo.get("email"),
        "picture": userinfo.get("picture"),
    }
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


def _proxy_gateway_request(url: str, req_headers: dict[str, str], body: dict, label: str) -> tuple[int, dict]:
    print(f"\n[{label}] POST {url}")
    print(f"[{label}] Headers: {req_headers}")
    print(f"[{label}] Request body: {body}")

    resp = requests.post(
        url,
        json=body,
        headers=req_headers,
        timeout=30,
    )
    print(f"[{label}] Response status: {resp.status_code}")
    print(f"[{label}] Response body: {resp.text[:500]}")
    try:
        resp_body = resp.json()
    except Exception:
        resp_body = {"raw": resp.text}

    return resp.status_code, resp_body


def _chat_tool_request_body(agent_name: str, message: str, argument_name: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
        "method": "tools/call",
        "params": {
            "_meta": {
                "agentIdentity": {
                    "name": agent_name,
                    "version": "1.0.0",
                }
            },
            "name": CHAT_TOOL_NAME,
            "arguments": {
                argument_name: message,
            },
        },
    }


def _call_chat_tool(url: str, req_headers: dict[str, str], agent_name: str, message: str, label: str) -> tuple[int, dict]:
    body = _chat_tool_request_body(agent_name, message, "message")
    return _proxy_gateway_request(
        url=url,
        req_headers=req_headers,
        body=body,
        label=f"{label} chat",
    )


@app.route("/api/gateway", methods=["POST"])
def gateway_request():
    if "token" not in session:
        if session.get("guest"):
            return jsonify({"error": "401 Unauthorized: This gateway is protected with Google login. Sign in with Google to continue."}), 401
        return jsonify({"error": "Not authenticated"}), 401

    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Invalid JSON body"}), 400

    token = session["token"]
    req_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        status_code, resp_body = _proxy_gateway_request(
            url=GATEWAY_URL,
            req_headers=req_headers,
            body=body,
            label="Google",
        )
        return jsonify({"status": status_code, "body": resp_body})
    except requests.exceptions.RequestException as e:
        print(f"[Google] Request error: {e}")
        return jsonify({"error": str(e), "status": 0, "body": {}}), 502


@app.route("/api/gateway/chat", methods=["POST"])
def gateway_chat_request():
    if "token" not in session:
        if session.get("guest"):
            return jsonify({"error": "401 Unauthorized: This gateway is protected with Google login. Sign in with Google to continue."}), 401
        return jsonify({"error": "Not authenticated"}), 401

    body = request.get_json(silent=True) or {}
    message = (body.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Missing chat message"}), 400

    req_headers = {
        "Authorization": f"Bearer {session['token']}",
        "Content-Type": "application/json",
    }
    try:
        status_code, resp_body = _call_chat_tool(
            url=GATEWAY_URL,
            req_headers=req_headers,
            agent_name="chat-client",
            message=message,
            label="Google",
        )
        return jsonify({"status": status_code, "body": resp_body})
    except requests.exceptions.RequestException as e:
        print(f"[Google] Chat request error: {e}")
        return jsonify({"error": str(e), "status": 0, "body": {}}), 502


# ── Entrypoint ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  Agent Gateway Chat UI")
    print(f"  Google flow:  http://localhost:{PORT}/")
    print(f"  Callback:     {REDIRECT_URI}")
    print(f"  Gateway (Google): {GATEWAY_URL}")
    print(f"{'='*60}\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)
