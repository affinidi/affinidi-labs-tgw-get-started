# auth0-mcp-surface — documentation

A browser chat app that authenticates the user with **Google OAuth** (the caller
context), then routes MCP requests through the **Affinidi Agent Gateway**, which
delegates **Auth0** credentials to the upstream MCP server on the user's behalf.

These docs are split into short, focused files (each under ~100 lines).

## Primary Guide

**[Main setup guide](../README.md)** — Complete step-by-step instructions for setting up the chat surface with Google OAuth caller context and Auth0 credential delegation.

## Supporting Documentation

| Doc                                                    | What it covers                                                     |
| ------------------------------------------------------ | ------------------------------------------------------------------ |
| [architecture.md](architecture.md)                     | Components, request flow, the three trust boundaries               |
| [authentication.md](authentication.md)                 | Google login, session cookie, callback + redirects                 |
| [delegation-and-consent.md](delegation-and-consent.md) | Auth0 delegation via the gateway, on-demand consent, access-denied |
| [deployment-topologies.md](deployment-topologies.md)   | Single-origin, two-server dev, split/proxied hybrid + ports        |
| [configuration.md](configuration.md)                   | Environment variable reference (frontend + backend)                |
| [cors-and-preflight.md](cors-and-preflight.md)         | Why POSTs are CORS-simple; the proxy preflight fix                 |
| [change-log.md](change-log.md)                         | What was changed in the latest work session                        |

## The 30-second version

1. User opens the frontend and clicks **Sign in with Google**.
2. Google redirects to the backend callback; the backend stores the Google token
   in an **httpOnly session cookie** and sends the browser to `/chat`.
3. The chat screen greets the user. The **first message** calls the backend,
   which proxies a JSON-RPC `tools/call` to the **Agent Gateway** with the Google
   token as a bearer.
4. The gateway verifies the Google JWT (caller context) and, if needed, returns
   `consent_required` with an Auth0 authorize URL (credential delegation).
5. Once delegation is granted, the gateway reaches the upstream MCP server and
   the answer comes back to the chat.

## Related

- Main setup guide: [../README.md](../README.md)
- Chat MCP server: [../mcp-server/README.md](../mcp-server/README.md)
