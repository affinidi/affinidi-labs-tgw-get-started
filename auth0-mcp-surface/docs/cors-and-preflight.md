# CORS & Preflight

In the split/proxied topology the frontend and backend are on **different
subdomains**, so browser requests are cross-origin and CORS applies.

## The backend CORS setup

FastAPI's `CORSMiddleware` allows the known origins (`FRONTEND_URL`,
`BACKEND_URL`, and localhost dev ports) with `allow_credentials=True`. Simple
requests (e.g. `GET /api/auth/me`) get the right
`Access-Control-Allow-Origin` header and work fine.

## The problem: preflight stripped by the proxy

`POST /api/gateway/chat` with `Content-Type: application/json` is a **non-simple**
request, so the browser sends a `OPTIONS` **preflight** first. Behind the octo
proxy, the preflight headers (`Access-Control-Request-Method`) were being
stripped, so `CORSMiddleware` didn't recognise the `OPTIONS` as a preflight and
let it fall through to the router:

```
OPTIONS /api/gateway/chat  →  405 Method Not Allowed
```

A `405` with no CORS headers shows up in the browser as a CORS error.

## The fix: make the POSTs CORS-simple

The frontend POSTs (`chat`, `gateway`) **no longer set**
`Content-Type: application/json`. With a string body and no custom header, fetch
defaults to `text/plain` — a CORS-safelisted content-type — so the request stays
**simple** and the browser issues **no preflight** at all.

- The actual `POST` response still gets `Access-Control-Allow-Origin` from the
  existing middleware (proven working by the `GET /api/auth/me` case).
- The backend needs **no change**: Starlette's `request.json()` parses the body
  regardless of the content-type.

See `frontend/src/lib/api.ts` — the `chat` and `gateway` methods.

## Alternative (not used)

A backend catch-all `OPTIONS /api/{path}` handler that returns the preflight
headers manually (independent of the stripped request header). Cleaner to avoid
the preflight from the frontend, so that path was chosen.
