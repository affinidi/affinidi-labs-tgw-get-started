# Phase 2 — Gateway Setup

> **Prerequisite:** Complete [Phase 1](../README.md) first and confirm the basic A2A flow is working.

This guide walks you through adding an Affinidi Trust Gateway in front of each agent. Your portals and agents do not change — you only update URLs in the env files.

## Table of Contents

- [Architecture](#architecture)
- [Step 1 — Setup Gateways and Fabric Connection](#step-1--setup-gateway-and-fabric-connection)
- [Step 2 — Setup Trust Registry](#step-trust-registry)
- [Step 3 — Create Policies](#step-3--create-surface-policies)
- [Step 4 — Add JWT Strategy](#step-entra)
- [Step 5 — Create A2A Surfaces](#step-5--create-a2a-surfaces)
- [Step 6 — Update Environment and Restart](#step-6--update-environment-and-restart)
- [Step 7 — Test With Gateway](#step-7--test-with-gateway)
- [Trust Registry Kill Switch](#big-feature-trust-registry-kill-switch)
- [What the Gateway Added](#what-the-gateway-added)

---

## Architecture

![with gateway](./images/diagram-with-gateway.jpg)
_alt: Full gateway architecture diagram showing Thatcher Gateway and Dexter Gateway with Access Point, Managed Agent, and Transit Point for each_

### What each checkpoint does

#### Thatcher Gateway — Inbound (Portal → Agent)

| Checkpoint        | What happens                                                                             |
| ----------------- | ---------------------------------------------------------------------------------------- |
| **Access Point**  | Validates Entra JWT, creates user identity context from claims                           |
| **Managed Agent** | Dispatch policy check (scp, action), creates agent identity VP with user + agent binding |
| → Thatcher Agent  | Request forwarded with injected VP in metadata                                           |

#### Thatcher Gateway — Outbound (Agent → Dexter)

| Checkpoint          | What happens                                                                             |
| ------------------- | ---------------------------------------------------------------------------------------- |
| **Managed Agent**   | Agent identity context from payload (`agentIdentity` fields)                             |
| **Transit Point**   | Trust Registry check (is target agent recognized?), outbound policy, workload binding VP |
| → Fabric Connection | Signed request forwarded to Dexter Gateway                                               |

Dexter Gateway repeats the same pattern for its inbound traffic.

---

## Steps

### Step 1 — Setup Gateway and Fabric Connection

→ Complete these feature guides in order:

1. [Create Agent Gateway](../../../feature-guide/gateway-guide.md)
2. [Create Mediator](../../../feature-guide/mediator-guide.md)
3. [Fabric Connection](../../../feature-guide/fabric-connection-guide.md)

If you already have gateways created, you can skip directly to the mediator and fabric connection guides.

You will create:

- A Mediator for didComm communication
- A gateway for **Org A (Thatcher)**
- A gateway for **Org B (Dexter)**
- A Fabric Connection between them using mediator

Also enable VP audit on each gateway from **Settings -> Security**.

![Gateway VP audit setting](images/gateway-security-enable-vp-audit.png)

Verification screenshots for this step:

After adding mediators on both gateways:

![Gateway mediators](images/gateway-mediators.png)

After establishing Fabric Connection between gateways:

![Gateway fabric connection](images/gateway-fabric.png)

---

### Step 2 — Setup Trust Registry {#step-trust-registry}

→ Follow [Trust Registry Guide](../../../feature-guide/trust-registry-guide.md)

On **each** gateway:

- Add an **Issuer** for your own organization. This is the issuer identity your gateway uses when it creates and signs verifiable presentations.
  Example: On Thatcher Gateway, add the `Thatcher Digital Department` issuer. On Dexter Gateway, add the `Dexter Digital Department` issuer.
- Add an **Authority** for the peer organization. This is the external issuer DID that your gateway trusts when validating the other gateway's identities through Trust Registry.
  Example: On Thatcher Gateway, add Dexter's department DID as an authority. On Dexter Gateway, add Thatcher's department DID as an authority.

Issuer creates your local department identity in the gateway. Authority imports the peer department DID into your gateway so it can be used for Trust Registry queries and trust checks.

> Note: Your Trust Registry setup should match the issuer and authority examples shown in the screenshots later in this guide.
> Note: You can use one Trust Registry for both gateways or maintain separate Trust Registries for each side. If you use separate Trust Registries, additional trust configuration is required.

Verification screenshots for this step:

After adding Trust Registry:

![Gateway trust registry](images/gateway-trust-registry.png)

After adding issuers:

![Gateway issuers](images/gateway-issuers.png)

After adding authorities (other department):

![Gateway authority](images/gateway-authority.png)

---

### Step 3 — Create Surface Policies

→ Follow [Create a Surface Policy](../../../feature-guide/policy-guide.md#create-a-surface-policy)

Create the following **surface policies** on each gateway.
![policies](images/polices.png)

#### Thatcher Gateway Surface Policies

1. **Name:** `Dexter gateway only`  
   **Type:** `Agent surfaces`  
   **Policy content:** Copy from [use-cases/secure-agent-communication/gateway-config/policies/gateway-only.rego](../gateway-config/policies/gateway-only.rego)
   Replace `<remote_gateway_did>` with Dexter Gateway DID.

**Note:** You can get Dexter Gateway DID from **Connections**. Open the **remote gateway** record (not local gateway) and copy the **Gateway DID**.

2. **Name:** `User Scope Policy`  
   **Type:** `Agent surfaces`  
   **Policy content:** Copy from [use-cases/secure-agent-communication/gateway-config/policies/user-scope-policy.rego](../gateway-config/policies/user-scope-policy.rego)

3. **Name:** `Simple Dispatch Policy`  
   **Type:** `Agent surfaces`  
   **Policy content:** Copy from [use-cases/secure-agent-communication/gateway-config/policies/simple-dispatch-policy.rego](../gateway-config/policies/simple-dispatch-policy.rego)

#### Dexter Gateway Surface Policies

1. **Name:** `Thatcher Gateway Only`  
   **Type:** `Agent surfaces`  
   **Policy content:** Copy from [use-cases/secure-agent-communication/gateway-config/policies/gateway-only.rego](../gateway-config/policies/gateway-only.rego)
   Replace `<remote_gateway_did>` with Thatcher Gateway DID.

**Note:** Similar to Thatcher setup, get Thatcher Gateway DID from **Connections** by opening the **remote gateway** record and copying the **Gateway DID**.

2. **Name:** `User Scope Policy`  
   **Type:** `Agent surfaces`  
   **Policy content:** Copy from [use-cases/secure-agent-communication/gateway-config/policies/user-scope-policy.rego](../gateway-config/policies/user-scope-policy.rego)

3. **Name:** `Acknowledge Policy`  
   **Type:** `Agent surfaces`  
   **Policy content:** Copy from [use-cases/secure-agent-communication/gateway-config/policies/acknowledge-policy.rego](../gateway-config/policies/acknowledge-policy.rego)

Verification screenshot for this step:

**Note:** The screenshot may include additional policies. As long as the policies listed above are present, your setup is correct.

![Gateway policies](images/gateway-policies.png)

---

### Step 4 — Add JWT Strategy {#step-entra}

→ Follow [jwt-strategy-guide.md](../../../feature-guide/jwt-strategy-guide.md)

Create the same JWT strategy on **both gateways**.
![policies](images/jwt-strategies.png)

**JWT strategy configuration:**

| Field           | Value                                                          |
| --------------- | -------------------------------------------------------------- |
| Name            | `Microsoft Entra Access Token`                                 |
| Expected Issuer | `https://sts.windows.net/{tenant_id}/`                         |
| JWT Source      | `Remote`                                                       |
| JWKS URI        | `https://login.microsoftonline.com/{tenant_id}/discovery/keys` |

Replace `{tenant_id}` with your Microsoft tenant ID.

Verification screenshot for this step:

After adding JWT strategies:
**Note:** The screenshot may include additional JWT strategies. As long as the above JWT strategy is present, your setup is correct.

![Gateway JWT strategies](images/gateway-jwt-stragies.png)

---

### Step 5 — Create A2A Surfaces

Create 2 surfaces on each gateway.

#### Thatcher Gateway Surfaces

Create these two surfaces on Thatcher Gateway:

1. **`Thatcher`** surface using config [use-cases/secure-agent-communication/gateway-config/thatcher-gateway.json](../gateway-config/thatcher-gateway.json)  
   **Purpose**: Primary surface for user-facing (portal) inbound traffic, from Access Point to the Thatcher agent, with outbound routing through Transit Point to Dexter over the gateway-to-gateway fabric.
2. **`Dexter -> Thatcher`** surface using config [use-cases/secure-agent-communication/gateway-config/thatcher-gateway-to-dexter.json](../gateway-config/thatcher-gateway-to-dexter.json)  
   **Purpose**: Dedicated inbound surface for calls arriving from Dexter Gateway over the fabric connection to the Thatcher agent.

#### Dexter Gateway Surfaces

Create these two surfaces on Dexter Gateway:

1. **`Dexter`** surface using config [use-cases/secure-agent-communication/gateway-config/dexter-gateway.json](../gateway-config/dexter-gateway.json)  
   **Purpose**: Primary surface for user-facing (portal) inbound traffic, from Access Point to the Dexter agent, with outbound routing through Transit Point to Thatcher over the gateway-to-gateway fabric.
2. **`Thatcher -> Dexter`** surface using config [use-cases/secure-agent-communication/gateway-config/dexter-gateway-to-thatcher.json](../gateway-config/dexter-gateway-to-thatcher.json)  
   **Purpose**: Dedicated inbound surface for calls arriving from Thatcher Gateway over the fabric connection to the Dexter agent.

#### How to Create an A2A Surface

1. Click **Surfaces** menu, then click **Add surface**.

![Add surface](images/surface-create-1.png)

2. Select **A2A Surface Starter Template** and click the next arrow.

![Select A2A starter template](images/surface-create-2.png)

3. Open the **Config** section, delete existing content, and paste one of the JSON files listed above.

![Paste surface JSON config](images/surface-create-3.png)

4. Open the **Surface** section to view the visual layout generated from config.

**Note:** If the visual view does not render correctly, click in the surface and make a small name change to refresh it.

![Visual surface view](images/surface-create-4.png)

5. Verify and update these element settings (if present in that surface):

- **Surface area**: Select **Issuer**

![Select issuer on surface](images/surface-create-5.png)

- **Managed Agent**: Set the target agent public URL for the selected surface.
  - Use the Thatcher agent public URL for surfaces `Thatcher` and `Dexter -> Thatcher`.
  - Use the Dexter agent public URL for surfaces `Dexter` and `Thatcher -> Dexter`.

![Configure managed agent endpoint](images/surface-create-6.png)

- **Transit Point**: Select your remote gateway and the remote surface

**Note:** If the remote surface on the remote gateway has not been created yet, temporarily set Endpoint Type to Direct URL, enter a placeholder HTTP URL, and save the surface. Once the remote gateway surface is ready, change the endpoint to Via gateway as shown below.
![Configure transit point](images/surface-create-7.png)
![Configure transit point](images/surface-create-7-1.png)

- **Caller Context**: Use JWT strategy **Microsoft Entra Access Token**
- **Policy Element**: Select the policy created in Step 3
- **Trust Check**: Select Trust Registry, set Authority ID as other department ID, and Entity ID as caller agent DID
  ![Configure trust check](images/surface-create-8.png)

- **Static Agent DID**: Open the agent card from the main surface Access Point URL (for `Thatcher` or `Dexter`),
  for example: https://{GATEWAY_URL}/agents/org-a/thatcher-agent/.well-known/agent-card.json
  Copy the `holder` DID, then set it in the opposite surface's **Static Agent Identity** element:
  Thatcher agent DID -> `Dexter -> Thatcher` surface
  Dexter agent DID -> `Thatcher -> Dexter` surface
  ![Configure static agent did](images/surface-create-9.png)
  ![Configure static agent did1](images/surface-create-10.png)

6. Save the surface.

Repeat the same process until all 4 surfaces are created (2 per gateway).

After creating the surfaces, **Note:**

- **Access Point URL** (for example, Thatcher inbound surface URL)
- **Transit Point outbound path** (for example, path used to route from local gateway to remote gateway)

After adding surfaces on both gateways:

![Gateway surfaces list](images/gateway-surfaces.png)

![Dexter to Thatcher surface](images/gateway-dexter-thatcher-surface.png)

![Thatcher to Dexter surface](images/gateway-thatcher-dexter-surface.png)

---

### Step 6 — Update Environment and Restart

Copy the Access Point and Transit Point URLs from the Thatcher surface and update the environment variables in `org-a.env`. Do the same using the Dexter surface values for `org-b.env`.

Update `org-a.env`:

| Variable                | Set to                                     | Why                                     |
| ----------------------- | ------------------------------------------ | --------------------------------------- |
| `NEXT_PUBLIC_AGENT_URL` | Access Point URL                           | Portal sends A2A through gateway        |
| `PEER_AGENT_URL`        | Transit Point outbound URL on your gateway | Agent forwards to peer via your gateway |

Repeat for `org-b.env` with Dexter's gateway URLs.

Then restart portals:

```bash
./run.sh
```

`org-a.env` looks like this:

```
NEXT_PUBLIC_AGENT_URL=https://thatcher-gateway.proxy.apse1.octo.affinidi.io/agents/org-a/thatcher-agent
PEER_AGENT_URL=https://thatcher-gateway.proxy.apse1.octo.affinidi.io/outbound/agents/org-a/dexter-agent
```

`org-b.env` looks like this:

```
NEXT_PUBLIC_AGENT_URL=https://dexter-gateway.proxy.apse1.octo.affinidi.io/agents/org-b/dexter-agent
PEER_AGENT_URL=https://dexter-gateway.proxy.apse1.octo.affinidi.io/outbound/agents/org-b/thatcher-agent
```

---

### Step 7 — Test With Gateway

1. Sign out of both portals (guest session won't have Entra token)
2. Click **Sign in with Microsoft** on both portals
3. Complete Entra login

![Thatcher to Dexter surface](images/with-gw-verify-1.png)

4. Send **"Tell Dexter: Hello from Thatcher!"** from Org A portal
5. On Org B portal, open **Agent Log** tab

You should now see:
![Thatcher to Dexter surface](images/with-gw-verify-2.png)

- An **Agent Identity ✓** badge on the message from Thatcher
- Click it to view the full **Verifiable Presentation** — gateway-attested proof of who sent the message

![Thatcher to Dexter surface](images/with-gw-verify-3.png)

![Thatcher to Dexter surface](images/with-gw-verify-4.png)

Also verify the agent identities created by the gateways:

- Thatcher agent identity
- Dexter agent identity
- User identity bound to the exchange

![Gateway-created identities (Thatcher, Dexter, user)](images/with-gw-verify-5.png)

![Gateway identity details verification](images/with-gw-verify-6.png)

Finally, verify Trust Registry records added by the gateway:

- The issuer is a recognized department in the gateway
- That issuer is authorized as an authority to register agents
- Thatcher agent is recognized under that issuer authority

![Trust Registry verification for issuer authority and Thatcher agent](images/with-gw-verify-7.png)

Below are a few audit and observability screenshots from the gateway:

![Gateway audit and observability view 1](images/with-gw-verify-8.png)

![Gateway audit and observability view 2](images/with-gw-verify-9.png)

![Gateway audit and observability view 3](images/with-gw-verify-10.png)

![Gateway audit and observability view 4](images/with-gw-verify-11.png)

![Gateway audit and observability view 5](images/with-gw-verify-12.png)

---

## BIG FEATURE: Trust Registry Kill Switch

This is a critical safety feature in cross-org communication.

If the Dexter agent goes rogue and is no longer recognized under Dexter's issuer/department in Trust Registry, you can effectively cut off communication without changing app code.

### Kill Switch Scenario

1. Dexter agent is removed (or no longer recognized) in Trust Registry under its department/issuer.

![Dexter agent no longer recognized in Trust Registry](images/kill-switch-1.png)

2. Thatcher agent tries to send a message to Dexter through Thatcher Gateway.
3. Thatcher Gateway performs Trust Registry check for the target identity.
4. Trust check fails because Dexter agent is not recognized by its issuer/department.
5. Gateway blocks the request with **403 Policy Denied**.
6. Gateway audit log records the failed Trust Registry verification.

![403 policy denied when trust check fails](images/kill-switch-2.png)

![Gateway audit log showing trust check failure](images/kill-switch-3.png)

This gives you an immediate operational kill switch: revoke trust in Trust Registry, and gateway-to-gateway calls are denied automatically.

---

## What the Gateway Added

|                     | Phase 1 (direct)             | Phase 2 (gateway)                       |
| ------------------- | ---------------------------- | --------------------------------------- |
| **Auth**            | None — anyone can call       | Entra JWT validated at Access Point     |
| **Scope**           | Not checked                  | `agent.access` required                 |
| **Action policy**   | Not checked                  | Only `send:message` allowed             |
| **Caller identity** | Self-declared (not verified) | Gateway-attested via VP                 |
| **Cross-org trust** | None                         | Trust Registry checked at Transit Point |
| **Agent identity**  | Self-declared                | Workload binding VP signed by gateway   |
| **Audit**           | Local agent log only         | Full gateway audit trail                |
