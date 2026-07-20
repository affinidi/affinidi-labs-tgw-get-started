# Authentication

The user authenticates with **Google OAuth**. This is the *caller context* — it
identifies who is making the request. The Trust Gateway verifies this identity.

## Flow

1. **Login page (`/`)** — on load, `init()` calls `/api/auth/me`. If already
   authenticated, it redirects straight to `/chat`.
2. **Sign in with Google** — the frontend requests `/api/auth/login`, which
   returns the Google authorization URL, then redirects the browser there.
3. **Google callback** — Google redirects to the backend at
   `/api/auth/callback`. The backend:
   - validates the `state` (CSRF protection),
   - exchanges the code for tokens,
   - stores the Google `id_token` in the session,
   - redirects the browser to `FRONTEND_URL/chat`.
4. **Chat guard** — `/chat` calls `/api/auth/me` on load; if not authenticated it
   bounces back to `/`.

## Token storage — httpOnly session cookie

The Google token is **never sent to the browser**. It lives in a signed,
httpOnly session cookie on the backend. The frontend only ever learns "am I
authenticated?" via `/api/auth/me`.

Why: this is immune to XSS token theft (JavaScript cannot read the token),
unlike storing a token in `localStorage`.

## Cookie policy (auto-computed)

The backend derives the cookie's `SameSite`/`Domain`/`Secure` from the frontend
and backend origins:

| Situation | Cookie policy |
|-----------|---------------|
| Same origin (single-origin) | host-only, `SameSite=Lax` |
| Sub-domains of one site | `Domain=<shared parent>`, `SameSite=Lax` |
| Genuinely different sites | `SameSite=None; Secure` |

For the split-subdomain deploy, set `SESSION_COOKIE_DOMAIN` to the shared parent
so both hosts share the cookie. See [configuration.md](configuration.md).

## No guest mode

"Continue as Guest" was removed. Every request to the gateway requires a signed
session (a real Google login). Unauthenticated calls get `401`.
