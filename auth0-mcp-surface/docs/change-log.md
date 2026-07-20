# Change Log — latest work session

Summary of the changes made to this demo, newest concerns first.

## 1. Removed guest mode

"Continue as Guest" is gone end-to-end.
- Frontend: removed the button + `guest()` method (`index.astro`), the `guest`
  API method and `MeResponse.guest` field (`api.ts`).
- Backend: removed `GET /api/auth/guest`, the guest session flag, and the guest
  branches in `_require_auth()` and `me()` (`main.py`).

## 2. Chat is the landing surface (no dashboard)

Login goes straight to `/chat`. The chat screen shows the user's identity — a
personalised welcome empty-state (avatar + first name) and an avatar ring in the
top bar. A separate dashboard was considered and dropped as unnecessary.

## 3. Access-denied card

`render.ts` now detects a gateway denial (`401`/`403`, or a JSON-RPC error worded
denied/unauthorised/forbidden) and shows a friendly red **"Access Denied"** card
instead of raw JSON. `consent_required` is excluded (that keeps its existing
"Authorise Access" card). See [delegation-and-consent.md](delegation-and-consent.md).

## 4. `make local-up` starts all three services

`local-up` now runs the frontend (`:5137`), backend (`:8642`), and MCP server
(`:9740`) together under one `Ctrl-C`. Previously it started only the backend and
MCP server, causing a `502` when opening the frontend proxy.

## 5. Env var rename (clarity)

- frontend `PUBLIC_API_BASE` → **`PUBLIC_BACKEND_URL`** (keeps required `PUBLIC_`
  prefix for Astro).
- backend `PUBLIC_BASE_URL` → **`BACKEND_URL`**.

Updated everywhere: `.env`, `.env.example`, `api.ts`, `main.py`, `Makefile`,
`README.md`, `docker-compose.yml`.

## 6. CORS preflight fix

Frontend POSTs are now CORS-simple (no `application/json` header) to avoid a
preflight the proxy was stripping. Full detail in
[cors-and-preflight.md](cors-and-preflight.md).

## Verification

- Frontend `npm run build` passes; backend `py_compile` clean.
- No leftover `guest`, `PUBLIC_API_BASE`, or `PUBLIC_BASE_URL` references.
