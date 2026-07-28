# Delegation & Consent

**Auth0 credential delegation is owned entirely by the Agent Gateway.** The app
does not manage it, does not check its status, and does not hold any Auth0
secrets. The app simply calls the MCP server behind the gateway; the gateway
handles delegation.

## How it works

1. The user sends their **first chat message**. Nothing hits the gateway before
   this — delegation is not pre-warmed.
2. The backend proxies a JSON-RPC `tools/call` (`name: "chat"`) to the gateway,
   with the Google token as `Authorization: Bearer`.
3. The gateway verifies the Google JWT (caller context), then decides whether it
   already has a delegated Auth0 credential for this user.

## Three outcomes at the first message

| Outcome              | What the user sees                                                                    |
| -------------------- | ------------------------------------------------------------------------------------- |
| **Success**          | A normal chat response.                                                               |
| **Consent required** | A **centered popup window** (500×700px) opens automatically for Auth0 authentication. |
| **Access denied**    | A red **"Access Denied"** card with the gateway's reason.                             |

### Consent required (on-demand) — Automatic Popup Flow

When the gateway needs the user to approve delegation, it returns
`consent_required` with an Auth0 `authorization_url`. The frontend **automatically
opens this URL in a popup window** (centered, 500×700px). The user authenticates
in the popup, Auth0 redirects to the Agent Gateway callback URL
(`https://sa-primary.trustgateway.affinidi.io/v1/identity/oauth/callback/chat-auth0-provider`),
the gateway stores the delegated token, and **the popup closes automatically**.

The frontend detects popup closure via polling (every 500ms) and **automatically
retries** the original request (after a 500ms delay). The retry succeeds because
the gateway now has the stored credential.

**Key UX improvement:** No manual retry needed — authentication and retry are
fully automated. The user only sees:

1. "🔐 Opening Auth0 authentication..." message
2. Popup window opens
3. User authenticates
4. Popup closes
5. Chat response appears

**Popup blocked scenario:** If the browser blocks the popup, an error message
appears with a manual fallback link to authenticate in a new tab.

### Access denied

If the gateway refuses (e.g. `401`/`403`, or a JSON-RPC error containing
denied/unauthorised/forbidden), the frontend shows a friendly card explaining the
Google sign-in is valid but upstream access was not granted — instead of dumping
raw JSON.

Detection lives in `frontend/src/lib/render.ts` (`accessDeniedReason`), and it
deliberately ignores `consent_required` (that is an expected step, not a denial).

## Why no delegation "status check"

Only the gateway knows delegation state, and the natural place to discover it is
the actual `tools/call`. A separate probe endpoint would add a redundant round
trip, so it was intentionally not built.
