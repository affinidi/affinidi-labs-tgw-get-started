# Test Agent Surface — Chat UI with Google OAuth + Glean via Trust Gateway

A browser-based chat app that authenticates the **user with Google OAuth**, then routes MCP requests through the **Affinidi Trust Gateway (TG)**, which handles Glean OAuth credential delegation transparently.

---

## Architecture

```
Browser (User)
  │
  │  1. Login with Google OAuth
  ▼
Flask App (localhost:8081 / ngrok URL)
  │  Google id_token → Bearer header
  ▼
Affinidi Trust Gateway
  │  Verifies Google JWT (jwt_bearer strategy)
  │  Injects agentIdentity from MCP payload
  │  Delegates Glean OAuth credentials on behalf of the user (consent_mode: on_demand)
  ▼
Glean MCP Server
```

**First request:** TG returns a `401 consent_required` with a Glean authorization URL.  
The UI shows an **"Authorise Glean Access →"** button. The user clicks it, approves access in Glean, and is redirected back to TG. TG stores the delegated token and all subsequent requests succeed automatically.

---

## Why Trust Gateway?

### 🔑 Credential Risk

> _"Where are credentials stored? Who controls them?"_

Without TG, API keys and tokens are exposed directly to agents with no central control. TG **secures, injects, and controls credentials at runtime** — agents never see the underlying secrets.

In this demo, your Glean OAuth token is stored and managed entirely by TG. The Flask app only holds a Google id_token; TG handles the Glean credential delegation on demand.

---

### 🪪 Identity — Who Is the Agent?

> _"We don't know who the assistant is"_

Without TG, any caller can claim to be any agent — there is no verification. TG **gives every agent a verified identity** — like an employee badge. In this setup, every request must carry a valid Google-issued JWT, and TG verifies it against Google's public JWKS before forwarding anything.

---

### 👤 User Context — Who Is the Agent Working For?

> _"Who is the assistant working for?"_

Without TG, an agent action has no traceable link to the human who triggered it. TG **binds every agent action to the authenticated user** — claims like `sub`, `email`, and `name` from the Google JWT are carried forward in a Verifiable Presentation injected into the request to Glean. Glean knows exactly which user is behind the request.

---

### 🔐 Credential Delegation

> _"The agent needs access to Glean — but we can't hand it the token directly"_

TG handles the full OAuth 2.0 Authorization Code flow with Glean on the user's behalf. When a user consents once, TG stores the delegated Glean token securely and injects it into every subsequent request automatically. The client app never touches the Glean token.

---

### 📊 Observability — Full Visibility

> _"We don't know what agents are doing"_

TG provides **full request/response logs, distributed traces, and payload inspection** — every call through the gateway is recorded. No more debugging in the dark.

---

### 📋 Audit & Compliance

> _"Can we prove what happened?"_

TG creates **audit-ready, tamper-proof logs** that answer: who did what, when, and using which access. This makes compliance reporting and incident investigation tractable.

---

## Prerequisites

- Python 3.10+
- A Google Cloud project (for OAuth 2.0 credentials)
- An Affinidi Trust Gateway instance
- A Glean admin account (to create an OAuth app)
- An ngrok account and auth token ([dashboard.ngrok.com](https://dashboard.ngrok.com/get-started/your-authtoken))

---

## Part 1 — External Service Setup

### 1.1 Create a Google OAuth Client

1. Go to [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
2. Click **Create Credentials → OAuth client ID**
3. Set **Application type** to **Web application**
4. Give it a name (e.g. `TG Chat App`)
5. Under **Authorised redirect URIs**, add a placeholder for now — you will update this once ngrok is running:
   ```
   http://localhost:8081/callback
   ```
6. Click **Create**
7. Copy the **Client ID** and **Client Secret** — you will need these in `.env`

> You will replace the redirect URI with your ngrok URL in [Part 2, Step 3](#3-register-the-ngrok-callback-in-google-cloud-console).

---

### 1.2 Create a Glean OAuth App

1. Go to [Glean Admin → Third-Party OAuth](https://app.glean.com/admin/third-party-oauth)
2. Click **Create OAuth App** (or **New App**)
3. Fill in:
   - **App name**: e.g. `Affinidi Trust Gateway`
   - **Redirect URI**: use a placeholder for now — you will get the exact TG callback URL after completing [Part 3, Step 2](#step-2--credential-provider-glean-oauth) and update it then
4. Note the **Client ID** and **Client Secret** — you will add these as TG secrets in [Part 3, Step 1](#step-1--add-secrets-in-tg)

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

# Trust Gateway MCP surface endpoint (from your TG dashboard — set after Part 3)
GATEWAY_URL=https://<your-tg-host>/<your-surface-route>

# ngrok auth token
NGROK_AUTH_TOKEN=your-ngrok-token

# Leave REDIRECT_URI blank for now — update after Step 2 below
```

### 2. Start the ngrok tunnel (Terminal 1)

The Google OAuth callback must be on a public HTTPS URL. ngrok provides this.

```bash
./run.sh ngrok
```

Copy the printed ngrok URL, e.g. `https://abc123.ngrok-free.app`, then update `.env`:

```env
REDIRECT_URI=https://abc123.ngrok-free.app/callback
```

### 3. Register the ngrok callback in Google Cloud Console

1. Go to [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
2. Open the **OAuth 2.0 Client ID** created in Part 1.1
3. Under **Authorised redirect URIs**, replace the localhost placeholder with:
   ```
   https://abc123.ngrok-free.app/callback
   ```
4. Save

### 4. Start the Flask app (Terminal 2)

```bash
./run.sh ui
```

Open the ngrok URL in your browser: `https://abc123.ngrok-free.app`

---

## Part 3 — Trust Gateway Setup

### Step 1 — Add Secrets in TG

Before creating the Glean credential provider, store the Glean OAuth credentials as secrets so they can be referenced securely.

In the TG dashboard → **Secrets → New**, create two secrets:

| Secret name           | Value                              |
| --------------------- | ---------------------------------- |
| `glean_client_id`     | Client ID from Glean OAuth app     |
| `glean_client_secret` | Client secret from Glean OAuth app |

---

### Step 2 — Credential Provider (Glean OAuth)

In the TG dashboard → **Identity → Credential Providers → New**:

| Field                          | Value                                                   |
| ------------------------------ | ------------------------------------------------------- |
| Name                           | `Glean OAuth`                                           |
| Provider Type                  | OAuth 2.0 — Authorization Code (3-legged, user consent) |
| Authorization Endpoint         | `https://<your-glean-tenant>.glean.com/oauth/authorize` |
| Token Endpoint                 | `https://<your-glean-tenant>.glean.com/oauth/token`     |
| Callback URL Host              | Select your TG public host from the dropdown            |
| Callback URL Route             | `glean-oauth`                                           |
| Client ID Secret               | Select `glean-client-id` (created in Step 1)            |
| Client Secret                  | Select `glean-client-secret` (created in Step 1)        |
| Enable automatic token refresh | ✅ On                                                   |

After saving, TG displays the generated **Callback URL** (read-only):

```
https://<your-tg-host>/v1/identity/oauth/callback/glean-oauth
```

**Go back to [Glean Admin → Third-Party OAuth](https://app.glean.com/admin/third-party-oauth)** and update the redirect URI of your OAuth app to this exact URL.

---

### Step 3 — JWT Verification Strategy (Google)

In the TG dashboard → **Identity → Verification Strategies → New**:

| Field           | Value                                        |
| --------------- | -------------------------------------------- |
| Name            | `Google OAuth`                               |
| Expected Issuer | `https://accounts.google.com`                |
| JWKS Source     | Remote URL                                   |
| JWKS URI        | `https://www.googleapis.com/oauth2/v3/certs` |

---

### Step 4 — MCP Surface

Create an MCP surface in the TG dashboard:

| Field                          | Value                                                                                      |
| ------------------------------ | ------------------------------------------------------------------------------------------ |
| Protocol                       | `mcp`                                                                                      |
| Caller Authentication          | `jwt_bearer` → select the **Google OAuth** strategy from Step 3                            |
| Target Endpoint                | `https://<your-glean-tenant>.glean.com/mcp/default`                                        |
| Identity Slot (inbound)        | `from_payload` → field `agentIdentity.name`                                                |
| Outbound Credential            | Select **Glean OAuth** (from Step 2), `consent_mode: on_demand`, inject as `bearer_header` |
| Workload Binding (user fields) | `sub`, `iss`, `aud`, `name`, `email`                                                       |

Copy the **surface route URL** shown in the TG dashboard and set it as `GATEWAY_URL` in your `.env`.

---

## First-Use Flow (Glean Consent)

1. Open the app and click **Sign in with Google**
2. Send any message (e.g. click **List Tools**)
3. TG returns a **401 Consent Required** — the UI shows an **"Authorise Glean Access →"** button
4. Click it — your browser redirects to the Glean consent page
5. Approve access — Glean redirects back to the TG callback URL
6. TG stores your delegated Glean credentials
7. Switch back to the app tab and resend your message — it now succeeds ✅

> **Subsequent sessions:** once consent is granted, TG reuses the stored token automatically (with refresh if enabled). The consent step only happens once per user.

---

## Environment Variables Reference

| Variable               | Required | Description                                                          |
| ---------------------- | -------- | -------------------------------------------------------------------- |
| `GOOGLE_CLIENT_ID`     | ✅       | Google OAuth 2.0 client ID (from Part 1.1)                           |
| `GOOGLE_CLIENT_SECRET` | ✅       | Google OAuth 2.0 client secret (from Part 1.1)                       |
| `REDIRECT_URI`         | ✅       | Your ngrok URL + `/callback`, registered in Google Cloud Console     |
| `GATEWAY_URL`          | ✅       | TG MCP surface endpoint URL (from TG dashboard after Part 3, Step 4) |
| `PORT`                 | —        | Local port (default `8081`)                                          |
| `FLASK_SECRET_KEY`     | —        | Flask session secret (auto-generated if not set)                     |
| `NGROK_AUTH_TOKEN`     | ✅       | ngrok auth token                                                     |

---

## MCP Request Format

The app sends standard JSON-RPC 2.0 MCP requests. The `agentIdentity` field in `_meta` is required by the TG surface identity slot:

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

TG extracts `agentIdentity.name`, verifies the Google JWT from the `Authorization: Bearer <id_token>` header, injects the delegated Glean token to the Glean MCP server, and includes a Verifiable Presentation of the user's identity.

---

## Troubleshooting

| Symptom                                         | Cause                                             | Fix                                                                                                         |
| ----------------------------------------------- | ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `State mismatch – possible CSRF attack`         | Session cookie lost across ngrok redirect         | Restart the app — state is now stored server-side                                                           |
| `401 consent_required` with `authorization_url` | User hasn't yet delegated Glean credentials to TG | Click the "Authorise Glean Access →" button in the chat UI                                                  |
| `401` after consent was already granted         | TG token expired, refresh disabled                | Enable automatic token refresh on the Glean credential provider in TG                                       |
| ngrok tunnel `exit code 1`                      | `NGROK_AUTH_TOKEN` not set                        | Set `NGROK_AUTH_TOKEN` in `.env`                                                                            |
| Glean OAuth app rejects the redirect URI        | TG callback URL not registered in Glean           | Add the TG callback URL in [Glean Admin → Third-Party OAuth](https://app.glean.com/admin/third-party-oauth) |
