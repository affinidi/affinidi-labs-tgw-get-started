# Agent Surface — Astro + Alpine.js chat, Google caller context, Auth0 delegation

A browser-based chat app that authenticates the **user with Google OAuth** (the
**caller context**), then routes MCP requests through the **Affinidi Trust
Gateway**, which delegates **Auth0** credentials to the upstream MCP server on
the user's behalf (the **credential delegation**).

This is the `poodle-chai` reimagining of the original `glean-mcp-surface` demo:

| Concern | Original (`glean-mcp-surface`) | This demo (`auth0-mcp-surface`) |
|---|---|---|
| Caller context | Google OAuth | **Google OAuth (unchanged)** |
| Credential delegation | Glean OAuth | **Auth0 OAuth** |
| Frontend | Flask HTML templates + inline JS | **Astro (static) + Alpine.js** |
| Backend | Flask monolith (HTML + API) | **FastAPI (API only)** |

---

## Architecture

```
┌─ Browser ─────────────────────────────────────────────────────────┐
│  Astro (static HTML) + Alpine.js                                   │
│  Pages: /  (login)   /chat   /callback                             │
└───────────────┬────────────────────────────────────────────────────┘
                │  fetch (credentials: include)   ← relative /api/* (same origin)
                ▼
┌─ FastAPI backend — serves the built UI + the API on ONE port ─────┐
│  http://localhost:8642   (single origin)                          │
│  GET  /api/auth/login      → Google OAuth URL                      │
│  GET  /api/auth/callback   → exchange code, set session, → /chat   │
│  GET  /api/auth/me         → current user                          │
│  GET  /api/auth/guest      → guest session                         │
│  GET  /api/auth/logout                                             │
│  POST /api/gateway         → proxy raw JSON-RPC to the gateway     │
│  POST /api/gateway/chat    → proxy a chat tools/call               │
└───────────────┬────────────────────────────────────────────────────┘
                │  Authorization: Bearer <Google id_token>
                ▼
┌─ Affinidi Trust Gateway ──────────────────────────────────────────┐
│  • Verifies the Google JWT           → CALLER CONTEXT              │
│  • Delegates Auth0 credentials       → CREDENTIAL DELEGATION       │
│    (consent_mode: on_demand)                                       │
└───────────────┬────────────────────────────────────────────────────┘
                ▼
        Target MCP Server (protected upstream)
```

**On-demand consent:** the first request that needs upstream access returns a
`consent_required` payload with an Auth0 `authorization_url`. The UI shows an
**"Authorise Access →"** button; the user approves in Auth0 and the gateway
stores the delegated token so subsequent requests succeed automatically.

> The app itself never sees Auth0 client credentials — those live in the Trust
> Gateway's secret store. The frontend only renders whatever `authorization_url`
> the gateway returns, so switching the upstream provider from Glean to Auth0 is
> primarily a **gateway configuration change** plus the branding in this UI.

---

## Prerequisites

- Python 3.10+
- Node.js 18+
- A Google Cloud project (OAuth 2.0 credentials) — for the caller context
- An Affinidi Trust Gateway instance
- An Auth0 tenant + application — for credential delegation (configured in the gateway)

---

## Part 1 — External service setup

### 1.1 Google OAuth client (caller context — unchanged)

1. [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials)
2. **Create Credentials → OAuth client ID → Web application**
3. Add authorised redirect URI: `http://localhost:8642/api/auth/callback`
   (and, for a public demo, `<PUBLIC_BASE_URL>/api/auth/callback`)
4. Copy the **Client ID** and **Client Secret** into `backend/.env`

### 1.2 Auth0 application (credential delegation — replaces Glean)

1. [Auth0 Dashboard → Applications](https://manage.auth0.com/) → **Create Application → Regular Web Application**
2. **Allowed Callback URLs:** your Trust Gateway callback, e.g. `https://<tgw-host>/oauth/callback`
   (this is the **gateway's** callback, not this app's)
3. (Optional) Create an **API** in Auth0 and note its identifier (audience)
4. Note the Auth0 **domain**, **Client ID**, and **Client Secret** — you'll add
   these as secrets in the Trust Gateway (Part 3)

---

## Part 2 — Run it

There are **two** processes:

| Service | Port | What it is |
|---|---|---|
| **Chat surface** (this dir) | `8642` | FastAPI backend + built Astro UI (the client) |
| **Chat MCP server** ([`mcp-server/`](mcp-server)) | `9740` | the `chat` tool (Bedrock-optional) — the tool backend |

The chat surface never calls the MCP server directly — it calls the **Trust
Gateway** (`GATEWAY_URL`), and the gateway routes to the chat MCP server. So both
run locally, each gets its own public proxy, and the **MCP proxy** is what you
register in the gateway.

Fill in secrets first: `cp backend/.env.example backend/.env` and set
`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GATEWAY_URL` (UI + guest mode
work without them for look-and-feel testing).

### Run both services (from the repo root)

```bash
make local-up     # chat backend :8642  +  chat MCP server :9740  (Ctrl-C stops both)
```

Individually: `make serve` (chat backend only) · `make mcp` (chat MCP server only) ·
`make dev` (frontend hot-reload + backend) · `make docker-up` (chat container).
`make local-down` frees `:8642`, `:5137`, `:9740`.

### The `chat` tool + optional LLM (AWS Bedrock)

The chat UI sends `tools/call name="chat"` to the chat MCP server ([`mcp-server/`](mcp-server)).
That `chat` tool answers via **AWS Bedrock when configured**, otherwise returns a
**stub** reply — so getting-started works with no LLM. To enable real answers, in
[`mcp-server/.env`](mcp-server/.env.example) set `BEDROCK_MODEL_ID` (+ AWS
credentials). The LLM is always *your* infra — a delegated user token can't bill a
user's personal LLM account; delegation unlocks the user's *data*, not their model.

> The tutorial `../mcp` server (calculator/weather, :11000) is separate and
> unrelated to this chat surface.

### Wire the chat MCP server into the gateway

1. `make local-up` (both services running).
2. Put each behind a public URL — your own proxy, or ngrok:
   `ngrok http 9740` (chat MCP server), and expose `:8642` for the chat UI.
3. Gateway dashboard → **Surfaces → Add Surface → MCP Surface Starter** →
   Managed Agent → **Endpoint Type: Direct URL** → **Endpoint URL = the chat MCP
   server's public/proxy URL** → save → copy the **Channel Route** URL.
   (See the root README "MCP Server via Agent Gateway" for the dashboard walkthrough.)
4. Set `GATEWAY_URL` in `backend/.env` to that **Channel Route** URL.
5. Reload the chat UI → type a message (→ `chat` tool) or click **List Tools**
   (shows `chat`).

> **Historical note:** the original `glean-mcp-surface` pointed the same chat UI
> at **Glean's** MCP server (Glean Assistant did the LLM/RAG), scoped per-user via
> Glean OAuth delegation. Our `chat` tool is the neutral, Bedrock-optional
> stand-in for that upstream assistant.

### Expose a public URL

`PUBLIC_BASE_URL` (chat backend) and `FRONTEND_URL` set the OAuth callback and
post-login redirect; register `<PUBLIC_BASE_URL>/api/auth/callback` in Google
Cloud Console. For a split across subdomains of one site, `SESSION_COOKIE_DOMAIN`
lets both share the session cookie. See `backend/.env.example`.

---

## Part 3 — Trust Gateway configuration

### 3.1 Caller context (JWT bearer — unchanged)

```yaml
strategy:
  type: jwt_bearer
  jwt_bearer:
    jwks_uri: https://www.googleapis.com/oauth2/v3/certs
    issuer: https://accounts.google.com
    audience: <google-client-id>
    claims_mapping: { subject: sub, email: email, name: name }
```

### 3.2 Credential delegation (Auth0 — replaces Glean)

```yaml
credential_provider:
  type: oauth2_authorization_code
  oauth2:
    authorization_url: https://<tenant>.auth0.com/authorize
    token_url:         https://<tenant>.auth0.com/oauth/token
    client_id:         <auth0-client-id>
    client_secret_ref: auth0-client-secret     # stored as a gateway secret
    redirect_uri:      https://<tgw-host>/oauth/callback
    scopes:            ["offline_access", "read:data", "write:data"]
    consent_mode:      on_demand
```

Add the Auth0 client secret to the gateway secret store as `auth0-client-secret`.

---

## Project layout

```
auth0-mcp-surface/
├── backend/                 # FastAPI: API + serves the built UI (single origin)
│   ├── main.py              # OAuth + gateway proxy + static mount
│   ├── requirements.txt
│   ├── run.sh
│   └── .env.example
├── frontend/                # Astro + Alpine.js
│   ├── src/
│   │   ├── pages/           # index (login) · chat · callback
│   │   ├── layouts/         # Layout.astro (imports the design system)
│   │   ├── lib/             # api.ts · render.ts
│   │   └── styles/
│   │       ├── design-system/  # vendored CSS design tokens (self-contained)
│   │       ├── assets/fonts/   # bundled woff2 fonts
│   │       └── global.css      # app-specific styles on top of the tokens
│   ├── astro.config.mjs
│   ├── package.json
│   └── .env.example
├── mcp-server/              # the chat MCP server (the `chat` tool, :9740)
│   ├── mcp_server.py        # JSON-RPC; chat → AWS Bedrock (optional) or stub
│   ├── requirements.txt
│   ├── run.sh
│   └── .env.example         # BEDROCK_MODEL_ID (optional), AWS_REGION, PORT
├── Dockerfile               # multi-stage: build UI → serve UI + API (one port)
├── docker-compose.yml       # single service on :8642
├── dev.sh                   # two-server hot-reload (used by `make dev`)
└── README.md
```

> Run both services from the repo root with `make local-up`, or
> `make dev` (hot reload). See "Part 2 — Run it".

## Styling — self-contained design tokens

The UI is styled with a **vendored CSS design-token system** under
`frontend/src/styles/design-system/` — a self-contained set of CSS custom
properties (surfaces, text, borders, buttons, spacing, typography, radius) plus
bundled fonts and a reset. There is **no external/registry dependency**: the CSS
is a local copy, so the repo builds anywhere with just `npm install`.

`Layout.astro` imports `design-system/globals.css` first, then `global.css` for
app-specific bits, and sets `data-theme="dark" data-product-theme="fabric"` on
`<html>`. Components reference semantic tokens directly (e.g.
`var(--surface-primary)`, `var(--button-primary-bg)`), so re-theming is a matter
of swapping token values — no component changes. Derived from an MIT-licensed
token system.

## Why Astro + Alpine.js (not Angular)?

The UI is a login screen plus a chat surface. Astro ships **zero JS by default**
and Alpine.js adds ~12 KB for the interactivity (state, events, conditional
rendering) with an Angular-like declarative feel — no build-heavy framework, no
client-side router. Richer SVG/animation work (e.g. a D3 request-flow banner)
slots in cleanly later without changing this foundation.
