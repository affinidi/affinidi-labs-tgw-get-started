# Deployment Topologies

The app supports **three** topologies. Pick one — do not mix them. Each expects
you to open a specific URL.

| Mode | Command | URL you open | `PUBLIC_BACKEND_URL` | Endpoints |
|------|---------|--------------|----------------------|-----------|
| **Single-origin** | `make local-up` | one URL (`:8642`) | `""` (relative) | 1 |
| **Two-server dev** | `make dev` | frontend `:5137` | `http://localhost:8642` | 2 (local) |
| **Split / proxied** | proxies | frontend proxy URL | backend proxy URL | 2 (public) |

## Ports

| Service | Port | What it is |
|---------|------|------------|
| Frontend (Astro dev) | `5137` | dev server (two-server / proxied modes) |
| Backend (FastAPI) | `8642` | API + serves built UI (single-origin) |
| Chat MCP server | `9740` | the `chat` tool, behind the gateway |

## Single-origin

`make local-up` builds the frontend to `dist/` with `PUBLIC_BACKEND_URL=""`, and
the FastAPI backend serves that UI on `:8642`. One origin → no CORS. It also
starts the frontend dev server and the MCP server so everything runs together.

## Two-server dev

`make dev` runs Astro on `:5137` (hot reload) and the backend on `:8642`. The
frontend calls the backend via `PUBLIC_BACKEND_URL=http://localhost:8642`.

## Split / proxied (the hybrid used in the demo)

Run the two dev servers locally, expose **each** behind its own proxy, and open
the **frontend** proxy URL:

- `…-frontend.proxy…` → `localhost:5137` (Astro dev)
- `…-backend.proxy…`  → `localhost:8642` (FastAPI)

Config (`backend/.env` + `frontend/.env`):
- `BACKEND_URL` = backend proxy URL (drives the OAuth callback)
- `FRONTEND_URL` = frontend proxy URL (post-login redirect target)
- `PUBLIC_BACKEND_URL` = backend proxy URL (frontend → backend calls)
- `SESSION_COOKIE_DOMAIN` = shared parent domain (cookie sharing)

## Common pitfalls

- **502 `upstream error: send request to local service`** — nothing is listening
  on `:5137`. Start the frontend (or `make local-up`).
- **Redirected to the backend host `/chat`** — you opened the backend URL
  directly while already logged in. Open the *frontend* URL for your topology.
