# Test Agent Surface — Chat UI with Google OAuth + Glean via Trust Gateway

A browser-based chat app that authenticates the **user with Google OAuth**, then routes MCP requests through the **Affinidi Trust Gateway (Agent Gateway)**, which handles Glean OAuth credential delegation transparently.

---

## Architecture

```
Browser (User)
  │
  │  1. Login with Google OAuth
  ▼
Glean Chat App (localhost:8081 or your public app URL)
  │  Google id_token → Bearer header
  ▼
Affinidi Trust Gateway
  │  Verifies Google JWT (jwt_bearer strategy)
  │  Injects agentIdentity from MCP payload
  │  Delegates Glean OAuth credentials on behalf of the user (consent_mode: on_demand)
  ▼
Glean MCP Server
```

**First request:** Agent Gateway returns a `401 consent_required` with a Glean authorization URL.  
The UI shows an **"Authorise Glean Access →"** button. The user clicks it, approves access in Glean, and is redirected back to Agent Gateway. Agent Gateway stores the delegated token and all subsequent requests succeed automatically.

---

## Why Trust Gateway?

### 🔑 Credential Risk

> _"Where are credentials stored? Who controls them?"_

Without Agent Gateway, API keys and tokens are exposed directly to agents with no central control. Agent Gateway **secures, injects, and controls credentials at runtime** — agents never see the underlying secrets.

In this demo, your Glean OAuth token is stored and managed entirely by Agent Gateway. The Glean Chat App only holds a Google id_token; Agent Gateway handles the Glean credential delegation on demand.

---

### 🪪 Identity — Who Is the Agent?

> _"We don't know who the assistant is"_

Without Agent Gateway, any caller can claim to be any agent — there is no verification. Agent Gateway **gives every agent a verified identity** — like an employee badge. In this setup, every request must carry a valid Google-issued JWT, and Agent Gateway verifies it against Google's public JWKS before forwarding anything.

---

### 👤 User Context — Who Is the Agent Working For?

> _"Who is the assistant working for?"_

Without Agent Gateway, an agent action has no traceable link to the human who triggered it. Agent Gateway **binds every agent action to the authenticated user** — claims like `sub`, `email`, and `name` from the Google JWT are carried forward in a Verifiable Presentation injected into the request to Glean. Glean knows exactly which user is behind the request.

---

### 🔐 Credential Delegation

> _"The agent needs access to Glean — but we can't hand it the token directly"_

Agent Gateway handles the full OAuth 2.0 Authorization Code flow with Glean on the user's behalf. When a user consents once, Agent Gateway stores the delegated Glean token securely and injects it into every subsequent request automatically. The client app never touches the Glean token.

---

### 📊 Observability — Full Visibility

> _"We don't know what agents are doing"_

Agent Gateway provides **full request/response logs, distributed traces, and payload inspection** — every call through the gateway is recorded. No more debugging in the dark.

---

### 📋 Audit & Compliance

> _"Can we prove what happened?"_

Agent Gateway creates **audit-ready, tamper-proof logs** that answer: who did what, when, and using which access. This makes compliance reporting and incident investigation tractable.

---

## Prerequisites

- Python 3.10+
- A Google Cloud project (for OAuth 2.0 credentials)
- An Affinidi Trust Gateway instance
- A Glean admin account (to create an OAuth app)

---

## Part 1 — External Service Setup

### 1.1 Create a Google OAuth Client

1. Go to [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
2. Click **Create Credentials → OAuth client ID**
3. Set **Application type** to **Web application**
4. Give it a name (e.g. `Agent Gateway Chat App`)
5. Under **Authorised redirect URIs**, add your callback URI:
   ```
   http://localhost:8081/callback
   ```
6. Click **Create**
7. Copy the **Client ID** and **Client Secret** — you will need these in `.env`

---

### 1.2 Create a Glean OAuth App

1. Go to [Glean Admin → Third-Party OAuth](https://app.glean.com/admin/third-party-oauth)
2. Click **Create OAuth App** (or **New App**)
3. Fill in:
   - **App name**: e.g. `Affinidi Trust Gateway`

- **Redirect URI**: use a placeholder for now — you will get the exact Agent Gateway callback URL after completing [Part 3, Step 2](#step-2--credential-provider-glean-oauth) and update it then

4. Note the **Client ID** and **Client Secret** — you will add these as Agent Gateway secrets in [Part 3, Step 1](#step-1--add-secrets-in-agent-gateway)

---

## Part 2 — Running the App

### 1. Configure environment variables

```bash
cd test-agent-surface
cp .env.example .env
```

Edit `.env`:

```env
# Google OAuth credentials (from Part 1.1)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Trust Gateway MCP surface endpoint (from your Agent Gateway dashboard — set after Part 3)
GATEWAY_URL=https://<your-agent-gateway-host>/<your-surface-route>

# OAuth redirect URI (must match Google OAuth settings)
REDIRECT_URI=http://localhost:8081/callback
```

### 2. Confirm callback URI in Google Cloud Console

1. Go to [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
2. Open the **OAuth 2.0 Client ID** created in Part 1.1
3. Under **Authorised redirect URIs**, confirm it includes:
   ```
   http://localhost:8081/callback
   ```
4. Save

### 3. Start the Glean Chat App

```bash
./run.sh ui
```

Open in your browser: `http://localhost:8081`

---

## Part 3 — Trust Gateway Setup

### Step 1 — Add Secrets in Agent Gateway

Before creating the Glean credential provider, store the Glean OAuth credentials as secrets so they can be referenced securely.

In the Agent Gateway dashboard → **Secrets → New**, create two secrets:

| Secret name           | Value                              |
| --------------------- | ---------------------------------- |
| `glean_client_id`     | Client ID from Glean OAuth app     |
| `glean_client_secret` | Client secret from Glean OAuth app |

---

### Step 2 — Credential Provider (Glean OAuth)

In the Agent Gateway dashboard → **Identity → Credential Providers → New**:

| Field                          | Value                                                   |
| ------------------------------ | ------------------------------------------------------- |
| Name                           | `Glean OAuth`                                           |
| Provider Type                  | OAuth 2.0 — Authorization Code (3-legged, user consent) |
| Authorization Endpoint         | `https://<your-glean-tenant>.glean.com/oauth/authorize` |
| Token Endpoint                 | `https://<your-glean-tenant>.glean.com/oauth/token`     |
| Callback URL Host              | Select your Agent Gateway public host from the dropdown |
| Callback URL Route             | `glean-oauth`                                           |
| Client ID Secret               | Select `glean-client-id` (created in Step 1)            |
| Client Secret                  | Select `glean-client-secret` (created in Step 1)        |
| Enable automatic token refresh | ✅ On                                                   |

After saving, Agent Gateway displays the generated **Callback URL** (read-only):

```
https://<your-agent-gateway-host>/v1/identity/oauth/callback/glean-oauth
```

**Go back to [Glean Admin → Third-Party OAuth](https://app.glean.com/admin/third-party-oauth)** and update the redirect URI of your OAuth app to this exact URL.

---

### Step 3 — JWT Verification Strategy (Google)

In the Agent Gateway dashboard → **Identity → Verification Strategies → New**:

| Field           | Value                                        |
| --------------- | -------------------------------------------- |
| Name            | `Google OAuth`                               |
| Expected Issuer | `https://accounts.google.com`                |
| JWKS Source     | Remote URL                                   |
| JWKS URI        | `https://www.googleapis.com/oauth2/v3/certs` |

---

### Step 4 — MCP Surface

Create an MCP surface in the Agent Gateway dashboard:

| Field                          | Value                                                                                      |
| ------------------------------ | ------------------------------------------------------------------------------------------ |
| Protocol                       | `mcp`                                                                                      |
| Caller Authentication          | `jwt_bearer` → select the **Google OAuth** strategy from Step 3                            |
| Target Endpoint                | `https://<your-glean-tenant>.glean.com/mcp/default`                                        |
| Identity Slot (inbound)        | `from_payload` → field `agentIdentity.name`                                                |
| Outbound Credential            | Select **Glean OAuth** (from Step 2), `consent_mode: on_demand`, inject as `bearer_header` |
| Workload Binding (user fields) | `sub`, `iss`, `aud`, `name`, `email`                                                       |

Copy the **surface route URL** shown in the Agent Gateway dashboard and set it as `GATEWAY_URL` in your `.env`.

---

## First-Use Flow (Glean Consent)

1. Open the app and click **Sign in with Google**
2. Send any message (e.g. click **List Tools**)
3. Agent Gateway returns a **401 Consent Required** — the UI shows an **"Authorise Glean Access →"** button
4. Click it — your browser redirects to the Glean consent page
5. Approve access — Glean redirects back to the Agent Gateway callback URL
6. Agent Gateway stores your delegated Glean credentials
7. Switch back to the app tab and resend your message — it now succeeds ✅

> **Subsequent sessions:** once consent is granted, Agent Gateway reuses the stored token automatically (with refresh if enabled). The consent step only happens once per user.

---

## Environment Variables Reference

| Variable               | Required | Description                                                                                    |
| ---------------------- | -------- | ---------------------------------------------------------------------------------------------- |
| `GOOGLE_CLIENT_ID`     | ✅       | Google OAuth 2.0 client ID (from Part 1.1)                                                     |
| `GOOGLE_CLIENT_SECRET` | ✅       | Google OAuth 2.0 client secret (from Part 1.1)                                                 |
| `REDIRECT_URI`         | ✅       | OAuth callback URI + `/callback`, registered in Google Cloud Console                           |
| `GATEWAY_URL`          | ✅       | Agent Gateway MCP surface endpoint URL (from the Agent Gateway dashboard after Part 3, Step 4) |
| `PORT`                 | —        | Local port (default `8081`)                                                                    |
| `FLASK_SECRET_KEY`     | —        | Glean Chat App session secret (auto-generated if not set)                                      |

---

## MCP Request Format

The app sends standard JSON-RPC 2.0 MCP requests. The `agentIdentity` field in `_meta` is required by the Agent Gateway surface identity slot:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {
    "_meta": {
      "agentIdentity": {
        "name": "my-client"
      }
    }
  }
}
```

Agent Gateway extracts `agentIdentity.name`, verifies the Google JWT from the `Authorization: Bearer <id_token>` header, injects the delegated Glean token to the Glean MCP server, and includes a Verifiable Presentation of the user's identity.

---

## Troubleshooting

| Symptom                                         | Cause                                                        | Fix                                                                                                                    |
| ----------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| `State mismatch – possible CSRF attack`         | Session cookie lost across OAuth redirect                    | Restart the app — state is now stored server-side                                                                      |
| `401 consent_required` with `authorization_url` | User hasn't yet delegated Glean credentials to Agent Gateway | Click the "Authorise Glean Access →" button in the chat UI                                                             |
| `401` after consent was already granted         | Agent Gateway token expired, refresh disabled                | Enable automatic token refresh on the Glean credential provider in Agent Gateway                                       |
| Glean OAuth app rejects the redirect URI        | Agent Gateway callback URL not registered in Glean           | Add the Agent Gateway callback URL in [Glean Admin → Third-Party OAuth](https://app.glean.com/admin/third-party-oauth) |
