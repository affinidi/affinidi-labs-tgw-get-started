# Architecture

## Components

- **Frontend** — Astro (static) + Alpine.js. Pages: `/` (login), `/chat`,
  `/callback`. Talks to the backend over `fetch` with `credentials: include`.
- **Backend** — FastAPI. Serves the Google OAuth flow, keeps the user's Google
  token in a signed session cookie, and proxies MCP calls to the Agent Gateway.
- **Agent Gateway** — Affinidi-hosted. Verifies the Google JWT and delegates
  Auth0 credentials to the upstream MCP server on demand.
- **Chat MCP server** — the `chat` tool (Bedrock-optional), sitting behind the
  gateway. The app never calls it directly.

## Request flow

```
Browser (Astro + Alpine)
   │  fetch (cookie)         relative or PUBLIC_BACKEND_URL
   ▼
FastAPI backend  ── Authorization: Bearer <Google id_token> ──▶ Agent Gateway
   │  session cookie holds the Google token                        │
   │                                                               ▼
   │                                        verifies Google JWT (caller context)
   │                                        delegates Auth0 creds (delegation)
   │                                                               │
   ▼                                                               ▼
serves built UI (single-origin)                          Upstream MCP server
```

## Four trust boundaries

1. **Caller context (Google OAuth)** — who the user is. The gateway verifies the
   Google JWT via Google's JWKS.
2. **Credential delegation (Auth0)** — access to the upstream service on the
   user's behalf. Owned entirely by the gateway; secrets live in its secret
   store, never in this app.
3. **Session** — the backend↔browser trust. A signed httpOnly cookie holds the
   Google token; the frontend only ever asks `/api/auth/me`.
4. **Origin reachability** — everything above assumes the MCP server is reachable
   *only* via the gateway. The server has no auth of its own; if its origin is
   publicly reachable, the three boundaries above can be bypassed by calling it
   directly. Lock the origin down before any non-local use — see the hardening
   note in the [main README](../README.md) Part 1.

## Backend API surface

| Route                    | Purpose                                                |
| ------------------------ | ------------------------------------------------------ |
| `GET /api/auth/login`    | Returns the Google OAuth URL                           |
| `GET /api/auth/callback` | Exchanges the code, sets session, redirects to `/chat` |
| `GET /api/auth/me`       | Current user + auth state                              |
| `GET /api/auth/logout`   | Clears the session                                     |
| `POST /api/gateway`      | Proxies a raw JSON-RPC body to the gateway             |
| `POST /api/gateway/chat` | Proxies a chat `tools/call` to the gateway             |
| `GET /api/health`        | Health + gateway-configured flag                       |

See [authentication.md](authentication.md) and
[delegation-and-consent.md](delegation-and-consent.md) for the flows.
