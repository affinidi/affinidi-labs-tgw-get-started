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

## Part 2 — Run the app

Fill in secrets first: `cp backend/.env.example backend/.env` and set
`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GATEWAY_URL` (the UI + guest
mode work without them for look-and-feel testing).

### Easiest — one command, one port (from the repo root)

```bash
make local-up            # builds the frontend, serves API + UI on ONE port
```

Open **http://localhost:8642**. The FastAPI backend serves both the built Astro
site and the `/api/*` routes (single origin), so there's just one URL to open,
forward, or tunnel.

### Development — hot reload (two servers)

```bash
make dev                 # frontend :5137 (hot reload) + backend :8642
```

Open **http://localhost:5137**.

### Docker

```bash
make docker-up           # single container on :8642
make docker-down
```

### Expose a public URL (ngrok or Codespaces)

Because it's single-origin, you only expose **one** port (`8642`):

```bash
# Local, via ngrok:
ngrok http 8642
make local-up PUBLIC_BASE_URL=https://<your-subdomain>.ngrok-free.app

# GitHub Codespaces:
#   run `make local-up`, then in the Ports tab set port 8642 → Public,
#   copy the https URL, and re-run:
make local-up PUBLIC_BASE_URL=https://<name>-8642.app.github.dev
```

`PUBLIC_BASE_URL` makes the app use that URL for the OAuth callback and
post-login redirect. Register `<PUBLIC_BASE_URL>/api/auth/callback` as an
authorised redirect URI in Google Cloud Console.

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
├── Dockerfile               # multi-stage: build UI → serve UI + API (one port)
├── docker-compose.yml       # single service on :8642
├── dev.sh                   # two-server hot-reload (used by `make dev`)
└── README.md
```

> Run it from the repo root with `make local-up` (single origin, one port) or
> `make dev` (hot reload). See "Part 2 — Run the app".

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
