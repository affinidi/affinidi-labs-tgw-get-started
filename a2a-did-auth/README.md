# A2A DID Auth Lab

A minimal, three-phase demo showing how Agent Gateway can protect an A2A agent
with **DID Auth** — with **zero changes to the agent itself**. Everything
(agent, portal, and the DID Auth caller flow) runs locally; only the gateway
piece needs a public URL.

- `agent.py` — a minimal A2A echo agent. It has no authentication code at all.
- `portal/` — a small web portal used to drive and visualize all three phases,
  showing the exact request/response at every step.

## Table of contents

- [Current flow vs. desired flow](#current-flow-vs-desired-flow)
- [Prerequisites](#prerequisites)
- [Getting started](#getting-started)
- [Phase A — Direct to Agent (no gateway)](#phase-a--direct-to-agent-no-gateway)
- [Phase B — Through the Gateway (no DID Auth yet)](#phase-b--through-the-gateway-no-did-auth-yet)
- [Phase C — Gateway + DID Auth](#phase-c--gateway--did-auth)
- [How the DID Auth flow works](#how-the-did-auth-flow-works)

## Current flow vs. desired flow

**Phase A flow** — you manually walk through three phases in the portal
to see how protection is added incrementally, without touching the agent:

```mermaid
graph LR
    Portal[Portal] -->|message/send, no auth| Agent[Echo Agent]
```

**Phase B flow (Gateway without DID Auth)** — the gateway simply proxies requests
to the agent without any authentication checks:

```mermaid
graph LR
  Portal[Portal] -->|message/send, no auth| Gateway[Agent Gateway - no auth]
  Gateway -->|forwards as-is| Agent[Echo Agent]
  Agent -->|response| Gateway
  Gateway -->|relays| Portal
```

**Phase C flow (Gateway with DID Auth)** — the gateway enforces DID Auth:
every caller must complete a challenge/response to get a session token before
the gateway will forward any A2A traffic:

```mermaid
graph LR
  Portal[Portal] -->|1 request challenge| Gateway[Agent Gateway - DID Auth enforced]
  Gateway -->|2 challenge| Portal
  Portal -->|3 sign locally| Portal
  Portal -->|4 authenticate with signed challenge| Gateway
  Gateway -->|5 session token| Portal
  Portal -->|6 message + Authorization token| Gateway
  Gateway -->|7 verified, forwards| Agent[Echo Agent]
  Agent -->|8 response| Gateway
  Gateway -->|9 relays| Portal
```

The agent code never changes across all three phases — only what sits in
front of it (nothing → gateway → gateway + DID Auth) changes.

## Prerequisites

- Python 3.10+
- An Agent Gateway instance, for Phases B and C (see
  [feature-guide/gateway-guide.md](../feature-guide/gateway-guide.md) if you
  don't have one yet)
- A public URL for the agent, for Phases B and C (ngrok, GitHub Codespaces, or
  any tunnel) — the gateway needs to reach your agent over the internet

## Getting started

```bash
cd a2a-did-auth
./run.sh
```

This starts both the Echo Agent and the DID Auth Portal, reading ports and
URLs from `.env`. Open the portal at `http://localhost:8090`.

---

## Phase A — Direct to Agent (no gateway)

Message goes straight from the portal to the agent. No gateway, no identity,
no headers.

1. After running the app, open the portal.
2. **Agent Info** shows what the agent does and its URL.

   ![Agent details](images/agent-info.png)

3. Switch to **Phase A** and chat directly with the agent.

   ![Chat with direct agent](images/agent-chat-direct.png)

> To move on to Phases B/C, the agent needs to be reachable via a public URL
> (ngrok, GitHub Codespaces, or similar) since Agent Gateway proxies it over
> the internet. Once you have a public URL, update `AGENT_URL` in `.env`.

---

## Phase B — Through the Gateway (no DID Auth yet)

Same plain message, now routed through a gateway surface that simply proxies
to the agent — no authentication is enforced yet.

**Prerequisite:** you need an Agent Gateway. If you don't have one, follow
[feature-guide/gateway-guide.md](../feature-guide/gateway-guide.md) to create
one first.

1. Log in to the gateway dashboard, select **Surfaces** on the left, then
   click **Add surface**.

   ![Add surface](images/phase-b-1.png)

2. Select **A2A surface** and click the arrow button — the gateway scaffolds
   a simple A2A surface for you.

   ![Select A2A surface](images/phase-b-2.png)

3. Select the surface area and give it a name, e.g. `A2A DID Auth Lab`.

   ![Name the surface](images/phase-b-3.png)

4. Select the **Managed Agent** element inside the surface area and enter
   your public agent URL under **Target Endpoint URL**.

   ![Set target endpoint](images/phase-b-4.png)

5. Select the **Access Point** element, choose a channel prefix (e.g.
   `agents`), enter a custom path of your choice, copy the resulting channel
   route, then click **Save**.

   ![Configure access point](images/phase-b-5.png)
   ![Copy access point route](images/phase-b-6.png)

6. Update `GATEWAY_AGENT_URL` in `.env` to the gateway access point URL, e.g.:

   ```env
   GATEWAY_AGENT_URL=https://thatcher-gateway.proxy.apse1.octo.affinidi.io/agents/finance/rigid
   ```

7. Restart the server (`./run.sh`), open the portal, and click the **Phase B**
   tab — you should see the gateway URL pre-filled.

   ![Phase B in the portal](images/phase-b-7.png)

8. Send a message to the agent via the gateway, and observe the traffic
   arriving at the gateway.

   ![Traffic through the gateway](images/phase-b-8.png)

---

## Phase C — Gateway + DID Auth

**Prerequisite:** Phase B must be completed first (the surface already
exists).

1. Open the A2A surface created in Phase B.

   ![Existing surface](images/phase-b-6.png)

2. Right now the surface is plain: requests come in through the access point
   and the gateway forwards them straight to the target Echo Agent.

   ![Plain surface, no auth](images/phase-c-1.png)

3. Add DID Auth to the access point so a valid DID Auth session token must be
   presented, otherwise the gateway rejects the request with `401`.

   Find the **Caller Context** element in the left palette, under
   **Security & Policy**. Drag it between the **Access Point** and the
   **Managed Agent**, set the authentication method to **DID Auth**, and
   click **Save surface**.

   ![Add Caller Context / DID Auth](images/phase-c-2.png)

4. Back in the portal, click the **Phase C** tab and try sending a message.
   This time the gateway responds with `401` because no DID Auth session
   token has been established yet — this is expected.

   ![401 without a session](images/phase-c-3.png)

5. Create a DID Auth session using the **Create Session** button. This walks
   through the DID Auth flow: **Request Challenge → Sign Challenge →
   Authenticate**.

   ![Create Session flow](images/phase-c-4.png)

6. Once a session token exists (with its own expiry), sending a message again
   works: the gateway receives the token, validates it, and forwards the
   request to the agent.

   ![Authenticated message succeeds](images/phase-c-5.png)

### How the DID Auth flow works

- **Caller Identity (DID)**: the portal creates (or reuses) a `did:key`
  identity for itself. This is a one-time setup, not part of each session.
- **Request Challenge**: the portal asks the gateway for a one-time,
  short-lived challenge tied to its DID.
- **Sign Challenge**: the portal signs the challenge locally with its DID's
  private key, producing a compact EdDSA JWS — no network call is made for
  this step.
- **Authenticate**: the portal submits the signed challenge to the gateway.
  If the signature is valid, the gateway issues a session token with an
  expiry.
- **Authenticated request**: every subsequent A2A message includes the
  session token in the `Authorization` header. The gateway verifies the
  token, resolves the caller's DID, applies any policy, and only then
  forwards the request to the agent — which never sees any of this and
  needs no changes.
