# Configuration

Two `.env` files: one for the backend, one for the frontend. Copy the
`.env.example` next to each and fill it in.

## Backend (`backend/.env`)

| Variable | Meaning |
|----------|---------|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth client (caller context) |
| `GATEWAY_URL` | Trust Gateway **Channel Route** URL (not the MCP server URL) |
| `BACKEND_URL` | This backend's own public base URL; drives the OAuth callback |
| `FRONTEND_URL` | Where the browser lands after login (split deploy only) |
| `SESSION_COOKIE_DOMAIN` | Shared parent domain so sub-domains share the cookie |
| `SESSION_SECRET` | Stable secret so sessions survive restarts |
| `PORT` | Server port (default `8642`) |
| `REDIRECT_URI` | Optional override; else derived from `BACKEND_URL` |

`BACKEND_URL` derivation: if set → `<BACKEND_URL>/api/auth/callback`; otherwise
→ `http://localhost:8642/api/auth/callback`. Register the resulting URL in the
Google Cloud Console.

## Frontend (`frontend/.env`)

| Variable | Meaning |
|----------|---------|
| `PUBLIC_BACKEND_URL` | Base URL of the backend the frontend calls |

`PUBLIC_BACKEND_URL` values:
- **unset** → dev default (`http://localhost:8642`)
- **`""`** → same origin / relative (single-origin build)
- **`https://host`** → explicit absolute base (split / proxied)

> The `PUBLIC_` prefix is **required** by Astro/Vite to expose the variable to
> browser code — do not remove it.

## Naming note

These were renamed for clarity:
- frontend `PUBLIC_API_BASE` → **`PUBLIC_BACKEND_URL`**
- backend `PUBLIC_BASE_URL` → **`BACKEND_URL`**

## Trust Gateway config (summary)

The gateway (not this app) is configured with:
- **Caller context**: `jwt_bearer` verifying Google's JWKS/issuer/audience.
- **Credential delegation**: `oauth2_authorization_code` for Auth0, with
  `consent_mode: on_demand`. Auth0 secrets live in the gateway's secret store.
