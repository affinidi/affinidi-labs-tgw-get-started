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
│  Astro (static HTML) + Alpine.js  →  http://localhost:4321         │
│  Pages: /  (login)   /chat   /callback                             │
└───────────────┬────────────────────────────────────────────────────┘
                │  fetch (credentials: include)
                ▼
┌─ FastAPI backend (API only) ──────────────────────────────────────┐
│  http://localhost:8000                                             │
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
3. Add authorised redirect URI: `http://localhost:8000/api/auth/callback`
4. Copy the **Client ID** and **Client Secret** into `backend/.env`

### 1.2 Auth0 application (credential delegation — replaces Glean)

1. [Auth0 Dashboard → Applications](https://manage.auth0.com/) → **Create Application → Regular Web Application**
2. **Allowed Callback URLs:** your Trust Gateway callback, e.g. `https://<tgw-host>/oauth/callback`
   (this is the **gateway's** callback, not this app's)
3. (Optional) Create an **API** in Auth0 and note its identifier (audience)
4. Note the Auth0 **domain**, **Client ID**, and **Client Secret** — you'll add
   these as secrets in the Trust Gateway (Part 3)

---

## Part 2 — Run the app

### Backend (FastAPI)

```bash
cd auth0-mcp-surface/backend
cp .env.example .env      # fill in GOOGLE_CLIENT_ID / SECRET and GATEWAY_URL
./run.sh                  # creates venv, installs deps, starts on :8000
```

### Frontend (Astro)

```bash
cd auth0-mcp-surface/frontend
cp .env.example .env      # PUBLIC_API_BASE=http://localhost:8000 (default is fine)
npm install
npm run dev               # starts on :4321
```

Open **http://localhost:4321** and sign in with Google.

> Or run both at once from the surface root: `./dev.sh`

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
├── backend/                 # FastAPI (API only)
│   ├── main.py              # OAuth + gateway proxy
│   ├── requirements.txt
│   ├── run.sh
│   └── .env.example
├── frontend/                # Astro + Alpine.js
│   ├── src/
│   │   ├── pages/           # index (login) · chat · callback
│   │   ├── layouts/         # Layout.astro
│   │   ├── lib/             # api.ts · render.ts
│   │   └── styles/          # global.css (design tokens)
│   ├── astro.config.mjs
│   ├── package.json
│   └── .env.example
├── dev.sh                   # run backend + frontend together
└── README.md
```

## Why Astro + Alpine.js (not Angular)?

The UI is a login screen plus a chat surface. Astro ships **zero JS by default**
and Alpine.js adds ~12 KB for the interactivity (state, events, conditional
rendering) with an Angular-like declarative feel — no build-heavy framework, no
client-side router. Richer SVG/animation work (e.g. a D3 request-flow banner)
slots in cleanly later without changing this foundation.
