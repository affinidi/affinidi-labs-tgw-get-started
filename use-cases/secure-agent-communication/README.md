# Cross-Org Secure Agent Communication

A hands-on lab that demonstrates secure, cross-organization agent-to-agent (A2A) communication using the [Affinidi Trust Gateway](https://docs.affinidi.com/products/affinidi-trust-fabric/agent-gateway/).

You will run two independent organizations — **Org A (Thatcher Corp)** and **Org B (Dexter Labs)** — each with their own portal and AI agent, and progressively secure the communication channel between them.

## Table of Contents

- [What You Will Build](#what-you-will-build)
- [Lab Structure](#lab-structure)
  - [Current Flow (Phase 1)](#current-flow-phase-1)
  - [Desired Flow (Phase 2)](#desired-flow-phase-2)
- [Prerequisites](#prerequisites)
- [Repository Structure](#repository-structure)
- [Phase 1 — Run Without Gateway](#phase-1--run-without-gateway)
  - [What's Next](#whats-next)
  - [run.sh Commands](#runsh-commands)
- [Phase 2 — Run With Gateway](./docs/gateway-setup.md)
- [Troubleshooting](#troubleshooting)

---

## What You Will Build

```
Org A                              Org B
┌─────────────────────┐           ┌─────────────────────┐
│  Thatcher Portal    │           │  Dexter Portal      │
│  (Entra login)      │           │  (Entra login)      │
└────────┬────────────┘           └─────────┬───────────┘
         │ A2A                              │ A2A
         ▼                                 ▼
┌─────────────────────┐  A2A  ┌─────────────────────────┐
│  Thatcher Agent     │──────►│  Dexter Agent           │
└─────────────────────┘       └─────────────────────────┘
```

Each portal lets a user chat with their own agent and forward messages to the peer agent across organizations.

> **Lab design note:** This lab uses a single shared agent codebase and a single shared portal codebase, each configured via environment variables to run as two separate organizations. In a real-world deployment each organization would maintain its own independent agent and portal. This shared approach keeps the lab simple and focused on the cross-org communication pattern.

> **No real LLM required:** The agents in this lab use hardcoded mock responses to simulate an AI model. When an agent detects a forwarding intent (e.g. "Tell Dexter..."), it makes a real A2A call to the peer agent. Everything else is a simulated response. This removes any LLM dependency so you can focus on the gateway communication pattern.

---

## Lab Structure

| Phase       | What you run                        | Goal                                  |
| ----------- | ----------------------------------- | ------------------------------------- |
| **Phase 1** | Agents + portals, direct connection | Understand the A2A flow               |
| **Phase 2** | Add Affinidi Trust Gateway          | Add auth, policy, identity, and trust |

➡ **Start here.** Complete Phase 1 before moving to [Phase 2 — Gateway Setup](./docs/gateway-setup.md).

---

## Current Flow (Phase 1)

```
Portal ──(Entra JWT)──► Agent ──────────────────────────► Peer Agent
    user authenticated        direct HTTP, no gateway checks
```

![without gateway](./docs/images/diagram-no-gateway.jpg)

Entra ID authenticates the user in Phase 1. The access token is passed through to the agent, but the agent does not validate it — it only passes it along. What's still missing:

- No token validation — anyone with the agent URL can call it
- No caller identity — the agent cannot verify who is sending
- No policy enforcement — any action, any payload is accepted
- No cross-org trust — no proof the message came from a legitimate org

---

## Desired Flow (Phase 2)

**Thatcher → Dexter**

```
Org A Portal ──► [Access Point] ──► [Managed Thatcher Agent] ──► [Transit Point] ──► Fabric ──► Dexter Gateway ──► Dexter Agent
                      │                         │                        │
                JWT validation           Trust check +          Outbound policy +
                User identity            Workload binding VP    Agent identity
```

**Dexter → Thatcher**

```
Org B Portal ──► [Access Point] ──► [Managed Dexter Agent] ──► [Transit Point] ──► Fabric ──► Thatcher Gateway ──► Thatcher Agent
                      │                        │                       │
                JWT validation          Trust check +          Outbound policy +
                User identity           Workload binding VP    Agent identity
```

![with gateway](./docs/images/diagram-with-gateway.jpg)

### Agent Gateway Runtime Architecture

What Agent Gateway is, how it governs AI agent interactions, and how to adopt it progressively with identity, policy, and observability controls.

![Agent Gateway runtime architecture](../../feature-guide/images/agent-gateway-arch.png)

---

## Prerequisites

- **Python 3.11+** and **Node.js 18+**
- A public HTTPS URL for each agent — see [Deploying Agents Publicly](#deploying-agents-publicly)
- **Azure Entra ID app registration** — needed for both phases (see [Entra Setup](#entra-id-setup))
- _(Phase 2 only)_ [Affinidi Developer Portal](https://portal.affinidi.com/) account

---

## Repository Structure

```
secure-agent-communication/
├── agent/                  # Shared Python A2A agent (runs as both Thatcher and Dexter)
│   ├── agent.py
│   └── requirements.txt
├── portal/                 # Shared Next.js portal (runs twice with different env)
│   └── src/
├── gateway-config/         # Reference surface configuration JSONs
│   ├── thatcher-a2a-surface.json
│   └── dexter-a2a-surface.json
├── org-a.env               # Org A (Thatcher Corp) configuration
├── org-b.env               # Org B (Dexter Labs) configuration
├── run.sh                  # Start / stop / status all services
└── docs/
    └── gateway-setup.md    # Phase 2: Gateway configuration guide
```

---

## Phase 1 — Run Without Gateway

Phase 1 is broken into four steps so you can verify each piece works before adding the next. The progression is:

| Step    | What changes                                | Goal                                   |
| ------- | ------------------------------------------- | -------------------------------------- |
| **1.1** | Nothing — just run locally with guest login | Verify the A2A flow works              |
| **1.2** | Add Entra ID login (agents still local)     | Verify real tokens flow end-to-end     |
| **1.3** | Deploy agents publicly                      | Get stable public URLs                 |
| **1.4** | Update env to use public agent URLs         | Final Phase 1 state, ready for Phase 2 |

---

### Step 1.1 — Clone and Run

```bash
git clone https://github.com/affinidi/affinidi-labs-tgw-get-started.git
cd affinidi-labs-tgw-get-started/use-cases/secure-agent-communication
./run.sh
```

That's it. `./run.sh` will:

1. Create `org-a.env` and `org-b.env` from the example files if they don't exist yet (localhost defaults, no Entra required)
2. Install all Python and Node.js dependencies
3. Start both agents and both portals

```
╔══════════════════════════════════════════════════════╗
║           Secure Agent Communication                 ║
╠══════════════════════════════════════════════════════╣
║  Org A (Thatcher)   Portal → http://localhost:3001   ║
║                     Agent  → http://localhost:8001   ║
╠══════════════════════════════════════════════════════╣
║  Org B (Dexter)     Portal → http://localhost:3002   ║
║                     Agent  → http://localhost:8011   ║
╚══════════════════════════════════════════════════════╝
```

> The env files created from examples have everything set to localhost and Entra fields left empty — perfect for Step 1.1. You will update specific values in later steps. The `★ CHANGE REQUIRED` and `★ FILL IN FROM STEP 1.2` comments in the files tell you exactly what to edit and when.

#### 1.1d — Test with Guest login

Open two browser windows (for example, in split view) to show both portals side by side:

- **Window 1** → `http://localhost:3001` (Org A — Thatcher Corp)
- **Window 2** → `http://localhost:3002` (Org B — Dexter Labs)

Click **Sign in as Guest** on both portals.

![Org portal login](./docs/images/phase1-login-org.png)
![Org portal dashboard](./docs/images/phase1-dasboard-org.png)

Try these prompts on Org A portal:

- **"Hi, how are you?"** — Thatcher agent responds
- **"Tell Dexter: Hello from Thatcher!"** — Thatcher forwards to Dexter, shows reply

On Org B portal, open the **Agent Log** tab — you should see the message that arrived from Thatcher.

![Chat showing 1](./docs/images/phase1-chat-thatcher-org-a.png)

![Chat showing 2](./docs/images/phase1-chat-thatcher-org-b.png)

✅ **If this works, the A2A flow is confirmed.** Move to Step 1.2.

---

### Step 1.2 — Add Entra ID Login (Agents Still Local)

In Phase 2, the gateway validates the Entra access token. Setting up Entra now means the same token that works in Phase 1 will work in Phase 2 — no changes needed later.

#### 1.2a — Create Azure App Registration

1. Go to [Azure Portal → App registrations](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps) → **New registration**
2. Under **Expose an API** → set Application ID URI: `api://<client-id>`
3. Add a scope: **`agent.access`**
4. Under **Authentication** → add Redirect URIs:
   - `http://localhost:3001/api/auth/callback/microsoft`
   - `http://localhost:3002/api/auth/callback/microsoft`
5. Under **Certificates & secrets** → create a client secret, copy the value

Reference: [Azure App Registration quickstart](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app)

![Chat showing 2](./docs/images/phase1-entra.png)

#### 1.2b — Update env files

Add to both `org-a.env` and `org-b.env`:

| Variable                  | Value                  |
| ------------------------- | ---------------------- |
| `MICROSOFT_CLIENT_ID`     | Your app's client ID   |
| `MICROSOFT_CLIENT_SECRET` | The secret you created |
| `MICROSOFT_TENANT_ID`     | Your Azure tenant ID   |
| `ENTRA_APP_ID_URI`        | `api://<client-id>`    |
| `ENTRA_SCOPE_NAME`        | `agent.access`         |

#### 1.2c — Restart and test with Microsoft login

```bash
./run.sh
```

Click **Sign in with Microsoft** (not Guest). Complete the Entra login on both portals.

Repeat the same test — send "Tell Dexter: Hello" from Org A. On Org B's Agent Log, open the **Headers** section of the inbound message — you should now see an `authorization: Bearer <token>` header. This confirms the real Entra token is flowing through agent-to-agent.

![Entra login dashboard](./docs/images/phase1-dasboard-org-entra.png)
![Agent dashboard headers](./docs/images/phase1-dasboard-org-entra2.png)

✅ **If tokens are flowing, move to Step 1.3.**

---

### Step 1.3 — Deploy Agents Publicly

Both agents need a public HTTPS URL so they can reach each other across networks. Choose one option:

#### Option A — ngrok (Quickest)

```bash
# Install ngrok: https://ngrok.com/download
./run.sh          # Start agents first
ngrok http 8001   # Expose Thatcher agent
# Note the https URL, e.g. https://abc123.ngrok.io
```

Repeat for Dexter (`ngrok http 8011`).

> ngrok free tier URLs change on restart. Run `ngrok config add-authtoken <token>` for persistent URLs.

#### Option B — GitHub Codespaces

1. Open repo in [GitHub Codespaces](https://github.com/codespaces)
2. Run `./run.sh` in the terminal
3. **Ports** tab → find 8001 and 8011 → set visibility to **Public**
4. Copy the forwarded HTTPS URLs

#### Option C — Google Cloud Run

Deploy `agent/` as a container using the [Cloud Run quickstart](https://cloud.google.com/run/docs/quickstarts). The deployed service URL becomes your `NEXT_PUBLIC_AGENT_URL`.

#### Verify agents are reachable

Before updating env files, confirm each agent responds:

```bash
curl https://<thatcher-public-url>/health
curl https://<dexter-public-url>/health
```

Both should return `{"status":"healthy","agent":"..."}`.

---

### Step 1.4 — Update Env to Use Public URLs

Update `org-a.env`:

| Variable                | Change to                         |
| ----------------------- | --------------------------------- |
| `NEXT_PUBLIC_AGENT_URL` | Thatcher agent's public HTTPS URL |
| `AGENT_INTERNAL_URL`    | Thatcher agent's public HTTPS URL |
| `PEER_AGENT_URL`        | Dexter agent's public HTTPS URL   |

Update `org-b.env` symmetrically (Dexter's public URL, Thatcher's as peer).

Restart portals only (agents are already running with their public URLs):

```bash
./run.sh
```

![agent-1 health](./docs/images/org-a-agent-health.png)
![agent-2 health](./docs/images/org-b-agent-health.png)

Repeat the test — sign in with Microsoft, send "Tell Dexter: Hello", verify Agent Log on Org B shows the message.

You should see your agent's public URL and the Agent Card link.

![agent-1 health](./docs/images/org-agent-card.png)
![agent-1 health](./docs/images/org-a-agent-card.png)

---

### What You've Observed at End of Phase 1

| Observation                           | Reality                                          |
| ------------------------------------- | ------------------------------------------------ |
| User is authenticated                 | ✅ Entra JWT issued                              |
| Token validated by agent              | ❌ Agent receives token but does not validate it |
| Anyone with the agent URL can call it | ✅ No gateway in front                           |
| Sender identity is self-declared      | ✅ Not attested by any third party               |
| Action policy                         | ❌ No checks                                     |
| Cross-org trust                       | ❌ No trust registry                             |
| Audit trail                           | Agent log only                                   |

These are exactly the gaps the gateway closes in Phase 2. Importantly, **you already have the Entra token flowing** — in Phase 2 you only add gateway URLs to the env files, and the gateway starts validating the same token automatically.

---

## What's Next

**[Phase 2 → Add Affinidi Trust Gateway](./docs/gateway-setup.md)**

The same portals and agents continue to work. You only update `NEXT_PUBLIC_AGENT_URL` and `PEER_AGENT_URL` to point to gateway URLs. The gateway adds:

- JWT validation at every hop
- Dispatch policy enforcement
- Gateway-attested Agent Identity (Verifiable Presentation)
- Cross-org trust via Trust Registry

---

## run.sh Commands

```bash
./run.sh              # Start all services (kills portal ports, keeps agents if running)
./run.sh force        # Kill all ports and start everything fresh
./run.sh stop         # Stop all services
./run.sh status       # Show what's running on known ports
./run.sh logs         # Tail all log files
```

> Portals take ~15 seconds to compile on first run.

---

## Troubleshooting

| Problem                                     | Cause                                        | Fix                                                   |
| ------------------------------------------- | -------------------------------------------- | ----------------------------------------------------- |
| Portal shows old org name after env change  | `NEXT_PUBLIC_*` vars are baked at startup    | `./run.sh force`                                      |
| `address already in use` on agent port      | Old process still holding port               | `./run.sh force`                                      |
| `SyntaxError: Unexpected end of JSON input` | Agent URL unreachable                        | Check `NEXT_PUBLIC_AGENT_URL` is accessible           |
| `401 Unauthorized` from agent               | Gateway rejecting token (Phase 2)            | Ensure Entra token has `agent.access` scope           |
| Agent Log shows empty                       | Messages going to deployed agent, not local  | Set `AGENT_INTERNAL_URL=http://localhost:PORT`        |
| `invalid_resource` on login                 | Wrong `ENTRA_APP_ID_URI`                     | Set to `api://<client-id>`, not the redirect URI      |
| `invalid_request` on login                  | Mixing `.default` scope with explicit scopes | Check `ENTRA_SCOPE_NAME=agent.access` (no `.default`) |
