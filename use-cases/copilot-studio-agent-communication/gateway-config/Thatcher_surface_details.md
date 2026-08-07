# Thatcher Surface

## Overview

**Surface Name:** Thatcher Surface  
**Surface ID:** `7dcf4aa2-267d-437f-8810-b61b80b3bc43`  
**Status:** Active  
**Protocol:** A2A (Agent-to-Agent)

The Thatcher Surface provides a secure ingress and routing layer for external agent communication. It authenticates callers, validates trust relationships, injects identity context, enforces policies, and routes requests to the managed Thatcher agent. Additionally, it provides an outbound transit path to the Dexter Surface.

---

# High-Level Architecture

```text
Human/User
    │
    ▼
worker-dexter
    │
    ▼
Access Point
    │
    ▼
Caller Authentication
    │
    ▼
Trust Validation
    │
    ▼
Policy Enforcement
    │
    ▼
Managed Agent (Thatcher)
    │
    ├── Inbound Requests
    │
    └── Outbound Requests
              │
              ▼
         Transit Point
              │
              ▼
      Metadata Extraction
              │
              ▼
       Identity Injection
              │
              ▼
       Workload Binding
              │
              ▼
         Dexter Surface
```

---

# Surface Components

## 1. Access Point

The Access Point is the public-facing entry to the Thatcher Surface.

### Configuration

| Property       | Value                                                          |
| -------------- | -------------------------------------------------------------- |
| Name           | External Access Point                                          |
| Protocol       | A2A                                                            |
| Route          | `/agents/copilot/Thatcher`                                     |
| Listen Address | `https://sanjay-primary.agent-6oduza.agentgateway.affinidi.io` |
| Route Prefix   | `/agents`                                                      |
| Route Suffix   | `copilot/Thatcher`                                             |

### Responsibilities

- Receives inbound agent traffic.
- Accepts requests from trusted external agents.
- Initiates authentication and trust validation.
- Routes validated requests to the target agent.

---

## 2. Caller Authentication

### Authentication Method

```yaml
type: api_key_provider
source: http_header
field: Authorization
```

### Request Format

```http
Authorization: <api-key>
```

### Responsibilities

- Validates API keys.
- Verifies caller identity.
- Prevents unauthorised surface access.

### Canvas Component

```text
Node Type: caller-auth
Node ID: caller-auth
```

---

## 3. Caller Trust Validation

A trust verification is executed immediately after authentication.

### Trust Registry

| Property    | Value                                  |
| ----------- | -------------------------------------- |
| Registry ID | `a17a1083-a7c7-4b7a-8590-b02fc51f468c` |
| Query Type  | Recognition                            |

### Trust Query

```json
{
  "authority_id": "did:webvh:QmTiBAwtQ2fDDV3WGbSP2twxCDovTASs2RFQkvRMyQiVKo:sanjay-primary.agent-6oduza.agentgateway.affinidi.io:issuers:316c57e7-8fd3-4bf4-8a0b-ef79c7c6df83",
  "entity_id": "{{ input.agent.did }}",
  "action": "is",
  "resource": "ownedAgent"
}
```

### Validation Purpose

Verifies:

- Agent ownership.
- Registration with trusted authorities.
- Valid DID association.

### Canvas Component

```text
Node Type: trust-check
Node ID: trust-check-caller
```

---

## 4. Policy Enforcement

Policy validation occurs before forwarding traffic to Thatcher.

### Configuration

```yaml
policy_definition_id: 746a09fa-38af-4d4c-a8a1-37e2e6091321
require_agent_context: true
```

### Responsibilities

- Enforces governance controls.
- Validates required context.
- Applies organisational security policies.

### Canvas Component

```text
Node Type: policy
Node ID: policy
```

---

## 5. Managed Agent Target

Represents the target agent endpoint.

### Configuration

| Property      | Value                                              |
| ------------- | -------------------------------------------------- |
| Name          | Thatcher                                           |
| Endpoint Type | A2A Proxy                                          |
| Endpoint      | `a2a-proxy://769cf3d8-67ea-47f4-b9cd-516db0c6a911` |
| Proxy ID      | `769cf3d8-67ea-47f4-b9cd-516db0c6a911`             |

### Features

#### Identity Injection

```yaml
inject_vp: true
```

Injects verified presentation credentials into requests.

#### Trust Registry Injection

```yaml
enabled: true
```

Attaches trust information automatically.

#### MCP Tool Policies

```yaml
mcp_tool_policies_enabled: false
```

No MCP policy controls enabled.

### Canvas Component

```text
Node Type: target
Node ID: target
```

---

## 6. Target Trust Verification

A secondary trust validation protects the destination agent.

### Trust Registry

| Property    | Value                                  |
| ----------- | -------------------------------------- |
| Registry ID | `944b1015-d56f-421a-a8d1-4f9689534446` |
| Query Type  | Recognition                            |

### Trust Query

```json
{
  "authority_id": "did:webvh:QmY97dhtBcW31Bu4e5z5s5YvZV76ZsJNa9H8XKVnLAm3Nb:canvas-delete.agent-6oduza.agentgateway.affinidi.io:issuers:d9e2e09c-b1dc-401f-9dff-b2e0e8214ce4",
  "entity_id": "{{ input.agent.did }}"
}
```

### Responsibilities

- Verifies trusted callers.
- Prevents unauthorised agent access.
- Establishes federated trust.

### Canvas Component

```text
Node Type: trust-check
Node ID: trust-check-target
```

---

## 7. Transit Point

Provides secure outbound routing to Dexter Surface.

### Configuration

| Property               | Value            |
| ---------------------- | ---------------- |
| Name                   | for Thatcher use |
| Alias                  | to-external      |
| Protocol               | A2A              |
| Transit Token Required | No               |

### Endpoint

```text
fabric://7417fad0-0892-460b-9f85-7b2e04396dc4/0982da7f-0d19-4eeb-9525-0caa5652fd1e
```

### Route

```text
/outbound/agents/transitpoint/to-dexter
```

### Remote Destination

| Item           | Value          |
| -------------- | -------------- |
| Remote Gateway | OrgB           |
| Remote Channel | Dexter Surface |

### Responsibilities

- Handles outbound agent communication.
- Securely routes requests to Dexter.
- Manages egress policies.

### Canvas Component

```text
Node Type: transit-point-a2a
Node ID: transit-point-a2a-1
```

---

## 8. Metadata Extraction

Extracts request metadata from headers.

### Extension

```text
https://fabric.affinidi.io/extensions/header-metadata/v1
```

### Header Mappings

| Header                                | Metadata Field   |
| ------------------------------------- | ---------------- |
| x-ms-entra-agent-id                   | entra_agent_id   |
| x-ms-client-tenant-id                 | client_tenant_id |
| x-ms-client-session-id                | session_id       |
| x-ms-correlation-id                   | correlation_id   |
| x-ms-coreframework-caller-activity-id | activity_id      |
| x-ms-apim-referrer                    | referrer         |

### Settings

```yaml
strip_mapped_headers: true
```

### Responsibilities

- Standardises metadata.
- Removes forwarded headers.
- Enables tracing and auditing.

### Canvas Component

```text
Node Type: metadata-extraction
Node ID: metadata-extraction-transit-point-a2a-1
```

---

## 9. Managed Identity Injection

Identity context is loaded from the request payload.

### Configuration

```yaml
type: from_payload
meta_field: agentIdentity
```

### Required Attributes

```yaml
entra_agent_id
client_tenant_id
```

### JSON Schema

```json
{
  "type": "object",
  "required": ["entra_agent_id", "client_tenant_id"]
}
```

### Responsibilities

- Preserves identity context.
- Supports multi-tenant routing.
- Enables downstream authorisation.

### Canvas Component

```text
Node Type: identity
Node ID: identity-transit-point-a2a-1-request
```

---

## 10. Outbound Authentication

The transit point authenticates to Dexter using a stored secret.

### Configuration

```yaml
method: static_secret
secret_id: dexter_access_point_api_key
header_name: Authorization
fallback: reject
```

### Request Format

```http
Authorization: <dexter_access_point_api_key>
```

### Responsibilities

- Authenticates outbound traffic.
- Protects Dexter endpoint.
- Rejects requests without valid credentials.

---

## 11. Workload Binding

Propagates caller identity and workload context.

### Configuration

```yaml
enabled: true
caller_source: authorization_bearer_jwt
chain_caller_credentials: true
```

### Forwarded Context

```text
sub
name
email
org
unique_name
scp
upn
given_name
```

### Responsibilities

- Preserves end-user identity.
- Supports delegated authorisation.
- Maintains end-to-end auditability.

### Canvas Component

```text
Node Type: workload-binding
Node ID: workload-binding-transit-point-a2a-1
```

---

## 12. Networking Controls

### Timeouts

| Setting         | Value      |
| --------------- | ---------- |
| Request Timeout | 90 seconds |
| Connect Timeout | 90 seconds |
| Idle Timeout    | 90 seconds |

### Retry Policy

```yaml
max_attempts: 3
```

### Responsibilities

- Protects against stalled requests.
- Improves resiliency.
- Handles transient failures.

### Canvas Component

```text
Node Type: networking
Node ID: networking-transit-point-a2a-1
```

---

## 13. Transit Security

### Request Signing

```yaml
sign_requests: true
```

Ensures:

- Request authenticity.
- Payload integrity.
- Non-repudiation.

### Transit Token Mode

```yaml
transit_token_mode: embedded
```

Provides embedded authorisation context within requests.

---

# Canvas Node Inventory

| Node ID                                   | Node Type             | Purpose                         |
| ----------------------------------------- | --------------------- | ------------------------------- |
| `__human__`                               | Human                 | Request originator              |
| `__caller__`                              | Caller                | Calling agent (`worker-dexter`) |
| `access-point`                            | Access Point          | External ingress                |
| `caller-auth`                             | Caller Authentication | API key verification            |
| `trust-check-caller`                      | Trust Check           | Validate trusted caller         |
| `policy`                                  | Policy                | Governance enforcement          |
| `target`                                  | Managed Agent         | Thatcher agent proxy            |
| `trust-check-target`                      | Trust Check           | Target-side trust verification  |
| `transit-point-a2a-1`                     | Transit Point         | Outbound routing                |
| `policy-transit-point-a2a-1`              | Policy                | Egress policy                   |
| `networking-transit-point-a2a-1`          | Networking            | Timeouts and retries            |
| `metadata-extraction-transit-point-a2a-1` | Metadata Extraction   | Header mapping                  |
| `identity-transit-point-a2a-1-request`    | Identity              | Identity propagation            |
| `workload-binding-transit-point-a2a-1`    | Workload Binding      | User context propagation        |
| `__managed-agent-npc__`                   | NPC Endpoint          | CPS Agent Thatcher              |
| `npc-endpoint-1`                          | NPC Endpoint          | Dexter Surface                  |

---

# End-to-End Request Flow

1. User or external agent (`worker-dexter`) invokes the Thatcher surface.
2. Access Point receives the incoming request.
3. API key authentication validates the caller.
4. Trust registry verifies agent ownership.
5. Policy engine validates governance requirements.
6. Request is forwarded to the Thatcher managed agent.
7. Thatcher performs processing.
8. If external communication is required, request enters the Transit Point.
9. Metadata is extracted from incoming headers.
10. Identity information is injected from the request payload.
11. Workload context is chained and preserved.
12. Outbound authentication is applied using the Dexter API key.
13. Request is cryptographically signed.
14. Request is sent to Dexter Surface.
15. Response returns through the same secured path.
