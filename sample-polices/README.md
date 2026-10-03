# OPA Policy Samples and Testing Guide

This guide explains what Agent Gateway policies are, how to create them, a set of
copy-paste policy samples for common scenarios, and how to test each one using the
built-in **dry run** feature in the Gateway dashboard.

Every sample below comes with:

- **What it does** - the scenario in one line.
- **Policy** - the Rego to paste into the policy editor.
- **Sample input** - a JSON `input` document to paste into the dry-run Test panel.
- **Expected result** - ALLOW or DENY, and what to change to flip it.

> For step-by-step dashboard screenshots of creating and attaching a policy, see the
> [Policy Guide](../feature-guide/policy-guide.md).
>
> For the complete field reference, see the
> [OPA policies reference](https://docs.affinidi.com/products/affinidi-trust-fabric/agent-gateway/reference/surfaces/opa-policies/).

---

## Table of Contents

- [1. Policy Basics](#1-policy-basics)
- [2. Create a Policy](#2-create-a-policy)
- [3. Test a Policy with Dry Run](#3-test-a-policy-with-dry-run)
- [4. Input Cheat Sheet](#4-input-cheat-sheet)
- [5. Policy Samples](#5-policy-samples)
  - [5.1 Require any authenticated caller](#51-require-any-authenticated-caller)
  - [5.2 Deny when caller authentication failed](#52-deny-when-caller-authentication-failed)
  - [5.3 Require a specific JWT scope](#53-require-a-specific-jwt-scope)
  - [5.4 Role and tenant based access from JWT claims](#54-role-and-tenant-based-access-from-jwt-claims)
  - [5.5 Allow only specific caller DIDs (DID auth)](#55-allow-only-specific-caller-dids-did-auth)
  - [5.6 Allow API key callers only](#56-allow-api-key-callers-only)
  - [5.7 Allow connections only from a specific gateway](#57-allow-connections-only-from-a-specific-gateway)
  - [5.8 Trust Registry check on inbound requests (caller leg)](#58-trust-registry-check-on-inbound-requests-caller-leg)
  - [5.9 Trust Registry check on outbound requests (target leg)](#59-trust-registry-check-on-outbound-requests-target-leg)
  - [5.10 Allow only specific users by email, or by role](#510-allow-only-specific-users-by-email-or-by-role)
    - [Variant: allow by email domain](#variant-allow-by-email-domain)
    - [Variant: allow by group or role claim](#variant-allow-by-group-or-role-claim)
  - [5.11 Restrict A2A actions](#511-restrict-a2a-actions)
  - [5.12 Restrict MCP tools](#512-restrict-mcp-tools)
  - [5.13 Method and path restrictions](#513-method-and-path-restrictions)
  - [5.14 Combined gateway policy: authenticated admin only](#514-combined-gateway-policy-authenticated-admin-only)
- [6. Common Mistakes](#9-common-mistakes)
- [7. Learn More](#10-learn-more)
- [8. Enterprise Entra ID Scenarios](#8-enterprise-entra-id-scenarios)
  - [8.1 Validate token identity on gateway calls](#81-validate-token-identity-on-gateway-calls)
  - [8.2 Require approved application identity (agent-to-gateway)](#82-require-approved-application-identity-agent-to-gateway)
  - [8.3 Block cross-tenant activity outside approved tenants](#83-block-cross-tenant-activity-outside-approved-tenants)
  - [8.4 Enforce tenant-aware delegated access](#84-enforce-tenant-aware-delegated-access)
  - [8.5 Require step-up authentication (MFA) for sensitive tools](#85-require-step-up-authentication-mfa-for-sensitive-tools)
  - [8.6 Block external and guest users](#86-block-external-and-guest-users)
  - [8.7 Restrict mutating actions by Entra directory role](#87-restrict-mutating-actions-by-entra-directory-role)
  - [8.8 Restrict privileged tools to approved builder groups](#88-restrict-privileged-tools-to-approved-builder-groups)
  - [8.9 Scenarios that need enrichment, not just the JWT](#89-scenarios-that-need-enrichment-not-just-the-jwt)

---

## 1. Policy Basics

A policy is a [Rego](https://www.openpolicyagent.org/docs/latest/policy-language/)
document that the gateway evaluates against a structured `input` object for every
request. If the policy does not produce `allow = true`, the request is denied.

There are two scopes:

| Scope             | Package                  | Where it runs                                               |
| ----------------- | ------------------------ | ----------------------------------------------------------- |
| **Gateway**       | `package gateway.policy` | Cluster-wide, on all matching traffic after authentication. |
| **Agent surface** | `package surface.policy` | On a specific surface, via a Policy element.                |

Evaluation order for an inbound request:

```
Caller -> Authentication -> Gateway policy -> Surface policy -> Managed Agent / Target
```

A deny at the gateway stage is final. A surface policy cannot override it.

### Minimum policy shape

```rego
package surface.policy

# Deny by default, then explicitly allow what you need.
default allow := false

allow if {
  # conditions
}
```

### Optional reason rules

The gateway surfaces `allow_reason` and `deny_reason` in the dry-run result, in
audit logs, and in the error response. Always add a `deny_reason` - it turns an
opaque 403 into something your team can debug.

```rego
allow_reason := "Request meets all requirements"

deny_reason := "Caller is not an admin" if {
  input.source_auth.claims.role != "admin"
}
```

> **Best practice:** start with `default allow := false` and allow explicitly.
> Never start with `default allow := true`.

---

## 2. Create a Policy

> Full walkthrough with dashboard screenshots: [Policy Guide](../feature-guide/policy-guide.md).

1. Open the Gateway dashboard and go to **Policies**.
2. Pick the tab for the scope you want:
   - **Gateway** -> **Define Gateway policy**
   - **Agent surfaces** -> **Define Agent surface policy**
3. Fill in:
   - **Name** - short and descriptive, e.g. `require-agent-access-scope`.
   - **Type** - Gateway or Agent surfaces.
   - **Description** - what it enforces and why.
   - **Policy content** - the Rego body.
4. Click **Create**.

Gateway policies apply immediately. For a surface policy you must also attach it:

1. Open the surface.
2. Select the **Policy** element on the edge you want to guard
   (inbound request, target request, response, or transit point).
3. Choose your policy definition.
4. Click **Save surface**.

Policies can be enabled or disabled without deleting them. Each save appends a new
version with its own content hash (`sha256:...`), so any decision can be traced back
to the exact Rego that produced it.

---

## 3. Test a Policy with Dry Run

The **Test** panel appears under the Rego editor once the policy has been saved at
least once. It lets you paste a sample `input` object, press **Run**, and see
**ALLOW** or **DENY** plus the reason - without touching live traffic.

Steps:

1. Open the policy in **Policies**.
2. Scroll to the **Test** panel.
3. Paste a sample input JSON (examples in every section below).
4. Click **Run against the draft above**.
5. Read the badge: **ALLOW** or **DENY**, plus `deny_reason` when defined.

Notes:

- The dry run evaluates the Rego **currently in the editor**, including unsaved
  changes. Nothing reaches the live policy engine.
- **Auto-run** re-evaluates shortly after every edit to the policy or the input.
- The button is disabled while the Rego does not compile or the JSON is invalid.
- The sample input is saved with the policy, so your last test input is still there
  next time.
- Draft size, input size, and run time are capped.

### Minimal starter input

This is the default sample the dashboard ships with:

```json
{
  "jwt": { "sub": "user@example.com", "role": "admin" },
  "http": { "method": "POST", "path": "/", "headers": {} },
  "gateway": { "direction": "inbound" }
}
```

> **Important:** `input.jwt` is **only** populated for MCP per-tool policies. For
> gateway and surface policies, JWT claims arrive under `input.source_auth.claims`.
> The starter input above is handy for a first `input.jwt.sub` smoke test, but real
> surface policies should be tested with the `source_auth` shape shown in
> [section 5.3](#53-require-a-specific-jwt-scope).

### Suggested test matrix

For each policy, run at least three inputs:

| Case                   | Purpose                                     |
| ---------------------- | ------------------------------------------- |
| Happy path             | Confirms ALLOW when every condition is met. |
| One condition wrong    | Confirms DENY and the right `deny_reason`.  |
| Field missing entirely | Confirms the policy fails closed, not open. |

---

## 4. Input Cheat Sheet

Fields the gateway populates in `input` for gateway and surface policies:

| Field                                          | Present when                              | Notes                                                     |
| ---------------------------------------------- | ----------------------------------------- | --------------------------------------------------------- |
| `input.http.method` / `.path` / `.headers`     | Always                                    | Sensitive headers are stripped.                           |
| `input.gateway.direction`                      | Always                                    | `"inbound"` or `"outbound"`.                              |
| `input.gateway.source_id`                      | Inbound via connection point, or outbound | Caller DID (inbound GW2) or managed agent DID (outbound). |
| `input.gateway.target_id`                      | Outbound / fabric send                    | Target URL or remote gateway DID.                         |
| `input.channel.config_id` / `.name`            | Always                                    | Surface identity.                                         |
| `input.source_auth.*`                          | Surface has a Caller Context element      | Shape depends on `method`.                                |
| `input.a2a.method` / `.message`                | A2A requests                              | Built from the original request body.                     |
| `input.mcp.method` / `.tool_name` / `.params`  | Inbound MCP requests                      |                                                           |
| `input.agent.*`                                | "Extract Trust Registry Data" enabled     | `did`, `trust_verification`, etc.                         |
| `input.trust_check_results.caller` / `.target` | Trust Check elements configured           | Arrays, never `null`.                                     |
| `input.extension_identity.*`                   | Verified VP in the request body           |                                                           |
| `input.identity_binding.*`                     | Verified VP from an upstream gateway      |                                                           |
| `input.metadata.*`                             | Metadata Injection rules ran              |                                                           |

### `input.source_auth` shapes

```json
{ "method": "jwt_bearer", "subject": "user@example.com", "claims": { "role": "admin" } }
{ "method": "api_key",    "key_name": "my-client-id" }
{ "method": "did_auth",   "did": "did:web:example.com:caller" }
{ "method": "mtls",       "principal": "CN=my-service,O=Example Corp", "fingerprint": "sha256:..." }
{ "method": "failed",     "attempted_method": "jwt_bearer", "reason": "Token has expired" }
```

> A failed authentication does **not** block the request on its own. The surface
> forwards it with no asserted caller identity unless a policy denies it. See
> [sample 5.2](#52-deny-when-caller-authentication-failed).

### Stripped headers

`input.http.headers` never contains `authorization`, `proxy-authorization`,
`cookie`, `set-cookie`, or any header whose name contains `token`, `secret`,
`credential`, `apikey`, or `api-key`. Use `input.source_auth` for identity, never
headers.

---

## 5. Policy Samples

### 5.1 Require any authenticated caller

**Scenario:** the simplest useful rule - reject anonymous traffic.

```rego
package surface.policy

import rego.v1

default allow := false

authenticated_methods := {"jwt_bearer", "api_key", "did_auth", "mtls"}

allow if {
  input.source_auth.method in authenticated_methods
}

allow_reason := sprintf("Authenticated via %s", [input.source_auth.method])

deny_reason := "Caller is not authenticated" if {
  not authenticated
}

authenticated if {
  input.source_auth.method in authenticated_methods
}
```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/a2a/tasks/send", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "user@example.com",
    "claims": { "scp": "agent.access" }
  }
}
```

**Sample input (DENY)** - remove the whole `source_auth` block, or set
`"method": "failed"`.

---

### 5.2 Deny when caller authentication failed

**Scenario:** a Caller Context element is configured but validation failed
(expired token, bad signature). Block it explicitly.

```rego
package surface.policy

import rego.v1

default allow := false

allow if {
  input.source_auth.method != "failed"
}

deny_reason := sprintf("Authentication failed (%s): %s", [
  input.source_auth.attempted_method,
  input.source_auth.reason,
]) if {
  input.source_auth.method == "failed"
}
```

**Sample input (DENY):**

```json
{
  "http": { "method": "POST", "path": "/", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" },
  "source_auth": {
    "method": "failed",
    "attempted_method": "jwt_bearer",
    "reason": "Token has expired"
  }
}
```

**Expected:** `DENY - Authentication failed (jwt_bearer): Token has expired`.

---

### 5.3 Require a specific JWT scope

**Scenario:** only tokens carrying the `agent.access` scope may reach the agent.
This is the most common enterprise rule (Entra ID / Auth0 / Okta all emit `scp`).

```rego
package surface.policy

import rego.v1

required_scope := "agent.access"

default allow := false

allow if {
  scope_permitted
}

allow_reason := "Request meets all requirements"

deny_reason := sprintf("Required scope '%s' not present in token", [required_scope]) if {
  not scope_permitted
}

scope_permitted if {
  scp := input.source_auth.claims.scp
  required_scope in split(scp, " ")
}
```

> Some IdPs emit scopes as an array (`scopes` / `scp` as a list) rather than a
> space-delimited string. Handle both:
>
> ```rego
> scope_permitted if {
>   required_scope in split(input.source_auth.claims.scp, " ")
> }
>
> scope_permitted if {
>   required_scope in input.source_auth.claims.scp
> }
> ```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/a2a/tasks/send", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": {
    "config_id": "10a0533d-b10b-4d02-a2fd-aaaaaaaad6e5",
    "name": "Thatcher"
  },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "wqjcIS4o5pPC95GXTLgfIIke6Y1RoQpEX",
    "claims": {
      "aud": "api://37b4d273-613b-4eaf-a975-5db4361f5787",
      "iss": "https://sts.windows.net/00000000-f06b-4a99-85d8-ca5481d17d2e/",
      "name": "Jane Doe",
      "upn": "jane.doe@example.com",
      "scp": "agent.access",
      "ver": "1.0"
    }
  }
}
```

**Sample input (DENY)** - change `"scp"` to `"user.read"`.
**Expected:** `DENY - Required scope 'agent.access' not present in token`.

---

### 5.4 Role and tenant based access from JWT claims

**Scenario:** only admins or operators from one tenant, and only on write paths.

```rego
package surface.policy

import rego.v1

allowed_roles := {"admin", "operator"}
allowed_tenant := "00000000-f06b-4a99-85d8-ca5481d17d2e"

default allow := false

allow if {
  role_permitted
  tenant_permitted
}

role_permitted if {
  object.get(input.source_auth, ["claims", "role"], "") in allowed_roles
}

tenant_permitted if {
  input.source_auth.claims.tid == allowed_tenant
}

deny_reason := "Caller role is not permitted on this surface" if {
  not role_permitted
}

deny_reason := "Caller belongs to an unrecognised tenant" if {
  role_permitted
  not tenant_permitted
}
```

`object.get` with a default keeps the rule defined even when the claim is missing,
so the `deny_reason` fires instead of the rule silently evaluating to `undefined`.

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "jane.doe@example.com",
    "claims": {
      "role": "admin",
      "tid": "00000000-f06b-4a99-85d8-ca5481d17d2e",
      "upn": "jane.doe@example.com"
    }
  }
}
```

**Sample input (DENY)** - set `"role": "viewer"` or change `tid`.

---

### 5.5 Allow only specific caller DIDs (DID auth)

**Scenario:** the surface uses DID auth in the Caller Context element and only a
known allowlist of agent DIDs may call it.

```rego
package surface.policy

import rego.v1

allowed_dids := {
  "did:web:example.com:agents:finance",
  "did:web:example.com:agents:support",
}

default allow := false

allow if {
  input.source_auth.method == "did_auth"
  input.source_auth.did in allowed_dids
}

allow_reason := sprintf("Caller DID %s is allowlisted", [input.source_auth.did])

deny_reason := "Caller did not present a DID credential" if {
  input.source_auth.method != "did_auth"
}

deny_reason := sprintf("Caller DID %s is not allowlisted", [input.source_auth.did]) if {
  input.source_auth.method == "did_auth"
  not input.source_auth.did in allowed_dids
}
```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/a2a/tasks/send", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" },
  "source_auth": {
    "method": "did_auth",
    "did": "did:web:example.com:agents:finance"
  }
}
```

**Sample input (DENY)** - change the DID to
`did:web:attacker.example.com:agents:rogue`.

---

### 5.6 Allow API key callers only

**Scenario:** a machine-to-machine surface where only named API key clients are
accepted.

```rego
package surface.policy

import rego.v1

allowed_clients := {"billing-worker", "etl-pipeline"}

default allow := false

allow if {
  input.source_auth.method == "api_key"
  input.source_auth.key_name in allowed_clients
}

deny_reason := "Surface accepts API key callers only" if {
  input.source_auth.method != "api_key"
}

deny_reason := sprintf("API key client '%s' is not permitted", [input.source_auth.key_name]) if {
  input.source_auth.method == "api_key"
  not input.source_auth.key_name in allowed_clients
}
```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/mcp", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "MCP Surface" },
  "source_auth": { "method": "api_key", "key_name": "billing-worker" }
}
```

---

### 5.7 Allow connections only from a specific gateway

**Scenario:** this surface is a connection point. Accept inbound traffic only from
one known remote gateway DID, and reject anything else.

```rego
package gateway.policy

import rego.v1

default allow := false

remote_gateway := "did:webvh:QmWCYMpgqdLGssPdgZBxti81QsYxxHRGmD1L1miizGgSNz:dexter-gateway.proxy.apse1.octo.affinidi.io:connection-points:b3bfd64e-0fa0-40ff-857b-eadeb8997fb6"

allow if {
  input.gateway.direction == "inbound"
  input.gateway.source_id == remote_gateway
}

allow_reason := "Inbound request from the expected peer gateway"

deny_reason := "Invalid gateway direction - expected inbound" if {
  input.gateway.direction != "inbound"
}

deny_reason := sprintf("Unexpected gateway source: %s", [input.gateway.source_id]) if {
  input.gateway.direction == "inbound"
  input.gateway.source_id != remote_gateway
}
```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/a2a/tasks/send", "headers": {} },
  "gateway": {
    "direction": "inbound",
    "source_id": "did:webvh:QmWCYMpgqdLGssPdgZBxti81QsYxxHRGmD1L1miizGgSNz:dexter-gateway.proxy.apse1.octo.affinidi.io:connection-points:b3bfd64e-0fa0-40ff-857b-eadeb8997fb6"
  },
  "channel": {
    "config_id": "96ab7082-5bb7-4a63-b881-cdc13abed1dd",
    "name": "Thatcher -> Dexter"
  }
}
```

**Sample input (DENY)** - set `"direction": "outbound"`, or change `source_id`.

> `input.gateway.source_id` is `null` on a plain inbound direct call from an
> external client. It is only populated when the request arrives through a
> connection point (caller DID) or on an outbound leg (managed agent DID).

---

### 5.8 Trust Registry check on inbound requests (caller leg)

**Scenario:** a Trust Check element on the caller leg verifies the incoming agent
against a trust registry. Allow only if every check passed.

```rego
package surface.policy

import rego.v1

default allow := false

allow if {
  caller_trusted
}

allow_reason := "Caller passed all Trust Registry checks"

deny_reason := "Caller failed Trust Registry verification" if {
  not caller_trusted
}

caller_trusted if {
  count(input.trust_check_results.caller) > 0
  every r in input.trust_check_results.caller { r.ok }
}
```

The `count(...) > 0` guard matters. `every` over an empty array is `true` in Rego,
so without it a misconfigured surface with no Trust Check element would allow
everything. Drop the guard only when you deliberately want "allow when no checks
are configured".

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/a2a/tasks/send", "headers": {} },
  "gateway": {
    "direction": "inbound",
    "source_id": "did:web:example.com:agents:thatcher"
  },
  "channel": {
    "config_id": "96ab7082-5bb7-4a63-b881-cdc13abed1dd",
    "name": "Thatcher -> Dexter"
  },
  "trust_check_results": {
    "caller": [
      {
        "id": "092f6a3e-5f48-4a4a-8d12-5ca2af58b7d2",
        "trust_registry_id": "fba52ad0-8e41-43fa-b5a8-64b2f92c4e57",
        "query_type": "recognition",
        "ok": true,
        "error": null,
        "name": "TP Trust Check",
        "authority_id": "did:web:authority.example.com",
        "entity_id": "did:web:example.com:agents:thatcher",
        "action": "is",
        "resource": "ownedAgent",
        "query_resolved": true
      }
    ],
    "target": []
  }
}
```

**Sample input (DENY)** - set `"ok": false`, or make `caller` an empty array.

---

### 5.9 Trust Registry check on outbound requests (target leg)

**Scenario:** your managed agent is calling an external agent through a Transit
Point. Verify the target is recognised by the trust registry before the call leaves.

Attach this policy to the **Managed Agent -> Target** edge (target policy slot).

```rego
package surface.policy

import rego.v1

default allow := false

allow if {
  input.gateway.direction == "outbound"
  target_trusted
}

allow_reason := sprintf("Target %s passed Trust Registry checks", [input.gateway.target_id])

deny_reason := "Expected an outbound request on this policy slot" if {
  input.gateway.direction != "outbound"
}

deny_reason := "Target failed Trust Registry verification" if {
  input.gateway.direction == "outbound"
  not target_trusted
}

target_trusted if {
  count(input.trust_check_results.target) > 0
  every r in input.trust_check_results.target { r.ok }
}
```

**Sample input (ALLOW):**

```json
{
  "http": {
    "method": "POST",
    "path": "/outbound/agents/org-a/dexter-agent/a2a/tasks/send",
    "headers": {
      "content-type": "application/json",
      "user-agent": "python-httpx/0.28.1"
    }
  },
  "gateway": {
    "direction": "outbound",
    "source_id": "did:web:example.com:agents:thatcher",
    "target_id": "fabric://b4ca99f8-0159-428b-bfff-aaaaf47fd0d5/96ab7082-5bb7-4a63-b881-cdc13abed1dd"
  },
  "channel": {
    "config_id": "10a0533d-b10b-4d02-a2fd-aaaaaaaad6e5",
    "name": "Thatcher"
  },
  "a2a": {
    "method": "message/send",
    "message": {
      "role": "user",
      "kind": "message",
      "messageId": "7c25f5264d7b4a00804a9b20a2fa83da",
      "parts": [
        {
          "kind": "data",
          "data": { "action": "send:message", "text": "Hello!" }
        }
      ]
    }
  },
  "trust_check_results": {
    "caller": [],
    "target": [
      {
        "id": "092f6a3e-5f48-4a4a-8d12-5ca2af58b7d2",
        "trust_registry_id": "fba52ad0-8e41-43fa-b5a8-64b2f92c4e57",
        "query_type": "recognition",
        "ok": true,
        "error": null,
        "name": "TP Trust Check",
        "authority_id": "did:web:authority.example.com",
        "entity_id": "did:web:partner.example.com:agents:dexter",
        "action": "is",
        "resource": "ownedAgent",
        "query_resolved": true
      }
    ]
  }
}
```

**Sample input (DENY)** - set `"ok": false` on the target result, or flip
`direction` to `"inbound"`.

---

### 5.10 Allow only specific users by email, or by role

**Scenario:** only a named list of people may call this surface. Everyone else is
denied, even with a valid token.

Different identity providers put the email in different claims, so normalise first:

| Provider                            | Claim to read                      |
| ----------------------------------- | ---------------------------------- |
| Entra ID (Azure AD) v1 tokens       | `upn`, falls back to `unique_name` |
| Entra ID v2 / Auth0 / Okta / Google | `email`                            |
| Any provider                        | `preferred_username`               |

```rego
package surface.policy

import rego.v1

allowed_emails := {
  "paramesh.k@affinidi.com",
  "jane.doe@affinidi.com",
}

default allow := false

allow if {
  email_permitted
}

allow_reason := sprintf("%s is on the allowlist", [caller_email])

deny_reason := "No email claim found on the token" if {
  caller_email == ""
}

deny_reason := sprintf("User '%s' is not on the allowlist", [caller_email]) if {
  caller_email != ""
  not email_permitted
}

email_permitted if {
  lower(caller_email) in allowed_emails
}

# Read the first email-bearing claim the IdP provided.
caller_email := e if {
  e := input.source_auth.claims.email
  e != ""
} else := e if {
  e := input.source_auth.claims.upn
  e != ""
} else := e if {
  e := input.source_auth.claims.unique_name
  e != ""
} else := e if {
  e := input.source_auth.claims.preferred_username
  e != ""
} else := ""
```

The allowlist is lowercased, and `lower(caller_email)` normalises the incoming
value, so `Paramesh.K@Affinidi.com` still matches.

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/a2a/tasks/send", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "wqjcIS4o5pPC95GXTLgfIIke6Y1RoQpEX",
    "claims": {
      "iss": "https://sts.windows.net/00000000-f06b-4a99-85d8-ca5481d17d2e/",
      "name": "Paramesh Kamarthi",
      "upn": "paramesh.k@affinidi.com",
      "unique_name": "paramesh.k@affinidi.com",
      "scp": "agent.access"
    }
  }
}
```

**Expected:** `ALLOW - paramesh.k@affinidi.com is on the allowlist`.

**Sample input (DENY)** - change `upn` and `unique_name` to
`someone.else@example.com`.
**Expected:** `DENY - User 'someone.else@example.com' is not on the allowlist`.

**Sample input (DENY, no email claim)** - delete both `upn` and `unique_name`.
**Expected:** `DENY - No email claim found on the token`.

#### Variant: allow by email domain

An allowlist of individuals does not scale. Gate on the domain instead, with an
optional explicit deny list for offboarded accounts.

```rego
package surface.policy

import rego.v1

allowed_domains := {"affinidi.com"}
blocked_emails := {"contractor.temp@affinidi.com"}

default allow := false

allow if {
  domain_permitted
  not lower(caller_email) in blocked_emails
}

domain_permitted if {
  parts := split(lower(caller_email), "@")
  count(parts) == 2
  parts[1] in allowed_domains
}

deny_reason := sprintf("'%s' is not from an allowed domain", [caller_email]) if {
  not domain_permitted
}

deny_reason := sprintf("'%s' is explicitly blocked", [caller_email]) if {
  domain_permitted
  lower(caller_email) in blocked_emails
}

caller_email := e if {
  e := input.source_auth.claims.email
  e != ""
} else := e if {
  e := input.source_auth.claims.upn
  e != ""
} else := ""
```

#### Variant: allow by group or role claim

Preferred over an email allowlist for anything beyond a small pilot - membership is
managed in the IdP, so the policy never needs editing when someone joins or leaves.

```rego
package surface.policy

import rego.v1

allowed_roles := {"agent-operators", "platform-admins"}

default allow := false

allow if {
  count(caller_roles & allowed_roles) > 0
}

allow_reason := "Caller holds a permitted role"

deny_reason := sprintf("None of the caller's roles %v are permitted", [caller_roles]) if {
  count(caller_roles & allowed_roles) == 0
}

# `roles` and `groups` arrive as arrays; a single `role` claim arrives as a string.
caller_roles := {r | some r in input.source_auth.claims.roles}

caller_roles := {r | some r in input.source_auth.claims.groups} if {
  not input.source_auth.claims.roles
}

caller_roles := {input.source_auth.claims.role} if {
  not input.source_auth.claims.roles
  not input.source_auth.claims.groups
  is_string(input.source_auth.claims.role)
}

caller_roles := set() if {
  not input.source_auth.claims.roles
  not input.source_auth.claims.groups
  not input.source_auth.claims.role
}
```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/a2a/tasks/send", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "paramesh.k@affinidi.com",
    "claims": {
      "upn": "paramesh.k@affinidi.com",
      "roles": ["agent-operators", "readers"]
    }
  }
}
```

**Sample input (DENY)** - change `roles` to `["readers"]`, or remove the claim.

---

### 5.11 Restrict A2A actions

**Scenario:** the surface speaks A2A. Only a defined set of actions may pass.

```rego
package surface.policy

import rego.v1

# Actions permitted through this surface
allowed_actions := {"send:message"}

default allow := false

allow if {
  a2a_action in allowed_actions
}

allow_reason := sprintf("A2A action '%s' is allowed", [a2a_action])

deny_reason := sprintf("A2A action '%s' is not allowed", [a2a_action]) if {
  not a2a_action in allowed_actions
}

# Extract action from message parts (data kind) or fall back to the a2a method
a2a_action := action if {
  some part in input.a2a.message.parts
  part.kind == "data"
  action := part.data.action
  is_string(action)
  action != ""
} else := action if {
  action := input.a2a.method
  is_string(action)
  action != ""
} else := "unknown"
```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/a2a/tasks/send", "headers": {} },
  "gateway": {
    "direction": "inbound",
    "source_id": "did:web:example.com:agents:thatcher"
  },
  "channel": {
    "config_id": "96ab7082-5bb7-4a63-b881-cdc13abed1dd",
    "name": "Thatcher -> Dexter"
  },
  "a2a": {
    "method": "message/send",
    "message": {
      "role": "user",
      "kind": "message",
      "messageId": "09092ba9ed7f4db080ef821b00000000",
      "parts": [
        {
          "kind": "data",
          "data": { "action": "send:message", "text": "Hello!" }
        }
      ]
    }
  }
}
```

**Sample input (DENY)** - change the action to `"delete:account"`.
**Expected:** `DENY - A2A action 'delete:account' is not allowed`.

---

### 5.12 Restrict MCP tools

**Scenario:** an MCP surface should expose only read-only tools.

```rego
package surface.policy

import rego.v1

read_only_tools := {"search", "fetch", "list_documents"}

default allow := false

# Non tools/call MCP traffic (initialize, tools/list) is allowed through.
allow if {
  input.mcp.method != "tools/call"
}

allow if {
  input.mcp.method == "tools/call"
  input.mcp.tool_name in read_only_tools
}

deny_reason := sprintf("MCP tool '%s' is not permitted on this surface", [input.mcp.tool_name]) if {
  input.mcp.method == "tools/call"
  not input.mcp.tool_name in read_only_tools
}
```

**Sample input (ALLOW):**

```json
{
  "http": {
    "method": "POST",
    "path": "/v1/surfaces/my-surface/mcp",
    "headers": {}
  },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "my-surface" },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "user@example.com",
    "claims": { "role": "analyst" }
  },
  "mcp": {
    "method": "tools/call",
    "tool_name": "search",
    "params": { "query": "hello" }
  }
}
```

**Sample input (DENY)** - change `tool_name` to `"delete_document"`.

> **Per-tool policies use a different input struct.** If you are attaching a policy
> to an individual tool binding (not the surface), use `input.mcp.method` for the
> tool name, `input.jwt.*` for claims, and `input.request.path`. See the
> [MCP tool policy input](https://docs.affinidi.com/products/affinidi-trust-fabric/agent-gateway/reference/surfaces/opa-policies/)
> section of the reference.

---

### 5.13 Method and path restrictions

**Scenario:** read-only surface - allow `GET`, and allow `POST` only on the A2A
send path.

```rego
package surface.policy

import rego.v1

default allow := false

allow if {
  input.http.method == "GET"
}

allow if {
  input.http.method == "POST"
  startswith(input.http.path, "/a2a/tasks/send")
}

deny_reason := sprintf("%s %s is not permitted on this surface", [
  input.http.method,
  input.http.path,
]) if {
  not method_path_permitted
}

method_path_permitted if {
  input.http.method == "GET"
}

method_path_permitted if {
  input.http.method == "POST"
  startswith(input.http.path, "/a2a/tasks/send")
}
```

**Sample input (DENY):**

```json
{
  "http": { "method": "DELETE", "path": "/a2a/tasks/cancel", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" }
}
```

---

### 5.14 Combined gateway policy: authenticated admin only

**Scenario:** cluster-wide baseline - every inbound request must be an
authenticated admin. This is a good first gateway policy to start from.

```rego
package gateway.policy

import rego.v1

default allow := false

allow if {
  input.gateway.direction == "inbound"
  input.source_auth.method == "jwt_bearer"
  input.source_auth.claims.role == "admin"
}

allow_reason := "Authenticated admin on an inbound request"

deny_reason := "Only inbound traffic is accepted" if {
  input.gateway.direction != "inbound"
}

deny_reason := "JWT bearer authentication is required" if {
  input.gateway.direction == "inbound"
  object.get(input, ["source_auth", "method"], "none") != "jwt_bearer"
}

deny_reason := "Caller is not an admin" if {
  input.source_auth.method == "jwt_bearer"
  object.get(input.source_auth, ["claims", "role"], "") != "admin"
}
```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "admin@example.com",
    "claims": { "role": "admin" }
  }
}
```

---

## 8. Enterprise Entra ID Scenarios

These scenarios enforce Microsoft Entra ID (Azure AD) enterprise controls using the
JWT the caller already presents under `input.source_auth.claims`. Some rely only on
standard Entra claims; others need an **optional claim** turned on in the app
registration's token configuration. Each sample says which claim to enable.

> **Why no Graph API calls here:** the gateway evaluates policies against the token
> it received - it does not call Microsoft Graph at request time. Checks that need
> live account state (`accountEnabled`, last sign-in, custom security attributes) are
> out of scope for a plain JWT policy. See
> [8.9 Scenarios that need enrichment](#89-scenarios-that-need-enrichment-not-just-the-jwt).

### 8.1 Validate token identity on gateway calls

**Scenario:** baseline zero-trust check - the token must come from the expected
tenant, audience, and client, and must not be close to expiry. Standard claims only,
no Entra configuration needed.

```rego
package surface.policy

import rego.v1

trusted_tenant := "00000000-f06b-4a99-85d8-ca5481d17d2e"
expected_audience := "api://37b4d273-613b-4eaf-a975-5db4361f5787"
approved_clients := {"37b4d273-613b-4eaf-a975-5db4361f5787"}

default allow := false

allow if {
  input.source_auth.method == "jwt_bearer"
  claims.tid == trusted_tenant
  claims.aud == expected_audience
  claims.appid in approved_clients
}

claims := input.source_auth.claims

deny_reason := "Caller did not present a JWT" if {
  input.source_auth.method != "jwt_bearer"
}

deny_reason := sprintf("Untrusted tenant '%s'", [claims.tid]) if {
  input.source_auth.method == "jwt_bearer"
  claims.tid != trusted_tenant
}

deny_reason := sprintf("Unexpected audience '%s'", [claims.aud]) if {
  input.source_auth.method == "jwt_bearer"
  claims.tid == trusted_tenant
  claims.aud != expected_audience
}

deny_reason := sprintf("Client '%s' is not approved", [claims.appid]) if {
  input.source_auth.method == "jwt_bearer"
  claims.tid == trusted_tenant
  claims.aud == expected_audience
  not claims.appid in approved_clients
}
```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/a2a/tasks/send", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "wqjcIS4o5pPC95GXTLgfIIke6Y1RoQpEX",
    "claims": {
      "tid": "00000000-f06b-4a99-85d8-ca5481d17d2e",
      "aud": "api://37b4d273-613b-4eaf-a975-5db4361f5787",
      "appid": "37b4d273-613b-4eaf-a975-5db4361f5787"
    }
  }
}
```

**Sample input (DENY)** - change `tid` to a different GUID.

---

### 8.2 Require approved application identity (agent-to-gateway)

**Scenario:** only a named set of agent service principals or managed identities may
call this surface, regardless of which user they act on behalf of.

```rego
package surface.policy

import rego.v1

approved_apps := {
  "37b4d273-613b-4eaf-a975-5db4361f5787",
  "a1b2c3d4-0000-1111-2222-333344445555",
}

default allow := false

allow if {
  input.source_auth.method == "jwt_bearer"
  app_id in approved_apps
}

# azp (authorized party) is used on v2 tokens; fall back to appid on v1 tokens.
app_id := id if {
  id := input.source_auth.claims.azp
  id != ""
} else := id if {
  id := input.source_auth.claims.appid
  id != ""
} else := ""

deny_reason := "No application identity claim (azp/appid) on the token" if {
  app_id == ""
}

deny_reason := sprintf("Application '%s' is not an approved agent identity", [app_id]) if {
  app_id != ""
  not app_id in approved_apps
}
```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/a2a/tasks/send", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "agent-app-sp",
    "claims": { "azp": "37b4d273-613b-4eaf-a975-5db4361f5787" }
  }
}
```

**Sample input (DENY)** - change `azp` to an unlisted app ID.

---

### 8.3 Block cross-tenant activity outside approved tenants

**Scenario:** only callers from your own tenant, or a short allowlist of partner
tenants, may use this surface.

```rego
package surface.policy

import rego.v1

approved_tenants := {
  "00000000-f06b-4a99-85d8-ca5481d17d2e", # home tenant
  "11111111-aaaa-bbbb-cccc-222222222222", # approved partner
}

default allow := false

allow if {
  input.source_auth.claims.tid in approved_tenants
}

deny_reason := sprintf("Tenant '%s' is not approved for this surface", [input.source_auth.claims.tid]) if {
  not input.source_auth.claims.tid in approved_tenants
}
```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "user@example.com",
    "claims": { "tid": "00000000-f06b-4a99-85d8-ca5481d17d2e" }
  }
}
```

**Sample input (DENY)** - change `tid` to `"99999999-0000-1111-2222-333344445555"`.

---

### 8.4 Enforce tenant-aware delegated access

**Scenario:** a delegated token's scopes must match both the required scope **and**
the tenant the request targets, so a token issued for tenant A cannot be replayed
against a surface scoped to tenant B.

```rego
package surface.policy

import rego.v1

required_scope := "agent.access"
resource_tenant := "00000000-f06b-4a99-85d8-ca5481d17d2e"

default allow := false

allow if {
  scope_permitted
  input.source_auth.claims.tid == resource_tenant
}

scope_permitted if {
  required_scope in split(input.source_auth.claims.scp, " ")
}

deny_reason := sprintf("Required scope '%s' missing from token", [required_scope]) if {
  not scope_permitted
}

deny_reason := "Token tenant does not match this surface's resource tenant" if {
  scope_permitted
  input.source_auth.claims.tid != resource_tenant
}
```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "user@example.com",
    "claims": { "scp": "agent.access", "tid": "00000000-f06b-4a99-85d8-ca5481d17d2e" }
  }
}
```

**Sample input (DENY)** - change `tid` to a different tenant, keeping the scope.

---

### 8.5 Require step-up authentication (MFA) for sensitive tools

**Scenario:** read-only paths need only a valid token; mutating/sensitive paths
require the token to show MFA in the `amr` (authentication methods reference)
claim.

```rego
package surface.policy

import rego.v1

sensitive_paths := {"/a2a/tasks/delete", "/admin"}

default allow := false

allow if {
  not sensitive_path
}

allow if {
  sensitive_path
  mfa_present
}

sensitive_path if {
  some p in sensitive_paths
  startswith(input.http.path, p)
}

mfa_present if {
  "mfa" in input.source_auth.claims.amr
}

deny_reason := "MFA is required for this operation" if {
  sensitive_path
  not mfa_present
}
```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/a2a/tasks/delete", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "user@example.com",
    "claims": { "amr": ["pwd", "mfa"] }
  }
}
```

**Sample input (DENY)** - change `amr` to `["pwd"]`.
**Expected:** `DENY - MFA is required for this operation`.

---

### 8.6 Block external and guest users

**Scenario:** only member (internal) accounts may use this surface; B2B guests and
external users are blocked.

> Requires the **`acct`** optional claim enabled on the app registration's token
> configuration (Entra ID emits `0` for member, `1` for guest).

```rego
package surface.policy

import rego.v1

default allow := false

allow if {
  input.source_auth.claims.acct == 0
}

deny_reason := "Guest and external accounts are not permitted on this surface" if {
  input.source_auth.claims.acct == 1
}

deny_reason := "Token has no 'acct' claim - enable it under optional claims" if {
  not input.source_auth.claims.acct
}
```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "user@example.com",
    "claims": { "acct": 0 }
  }
}
```

**Sample input (DENY)** - change `"acct": 0` to `"acct": 1`.

---

### 8.7 Restrict mutating actions by Entra directory role

**Scenario:** `GET` requests are open to any authenticated caller; mutating verbs
require an approved directory role.

> Requires **`wids`** (directory role template IDs) as an optional claim, or an app
> role mapped through **`roles`**. Common built-in role template IDs:
>
> | Role | Template ID |
> | --- | --- |
> | Global Administrator | `62e90394-69f5-4237-9190-012177145e10` |
> | Privileged Role Administrator | `e8611ab8-c189-46e8-94e1-60213ab1f814` |
> | User Administrator | `fe930be7-5e62-47db-91af-98c3a49a38b1` |
> | Application Administrator | `9b895d92-2cd3-44c7-9d02-a6ac2d5ea5c3` |

```rego
package surface.policy

import rego.v1

approved_role_ids := {
  "62e90394-69f5-4237-9190-012177145e10", # Global Administrator
  "e8611ab8-c189-46e8-94e1-60213ab1f814", # Privileged Role Administrator
  "fe930be7-5e62-47db-91af-98c3a49a38b1", # User Administrator
}

mutating_methods := {"POST", "PUT", "PATCH", "DELETE"}

default allow := false

allow if {
  not input.http.method in mutating_methods
}

allow if {
  input.http.method in mutating_methods
  caller_has_approved_role
}

caller_has_approved_role if {
  some id in input.source_auth.claims.wids
  id in approved_role_ids
}

deny_reason := "Caller does not hold an approved administrative role for mutating actions" if {
  input.http.method in mutating_methods
  not caller_has_approved_role
}
```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/a2a/tasks/send", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "admin@example.com",
    "claims": { "wids": ["fe930be7-5e62-47db-91af-98c3a49a38b1"] }
  }
}
```

**Sample input (DENY)** - set `"wids": []`.

---

### 8.8 Restrict privileged tools to approved builder groups

**Scenario:** only members of a platform-operations or builder group may call
privileged MCP tools.

> Requires the **`groups`** optional claim on the token. By default Entra emits at
> most 200 group object IDs directly in the token; larger tenants get a "groups
> overage" claim instead and need a Graph lookup, which puts this case into
> [8.9](#89-scenarios-that-need-enrichment-not-just-the-jwt) for those tenants.

```rego
package surface.policy

import rego.v1

approved_groups := {"11111111-2222-3333-4444-555555555555"}
privileged_tools := {"delete_resource", "rotate_secret", "export_data"}

default allow := false

allow if {
  input.mcp.method != "tools/call"
}

allow if {
  input.mcp.method == "tools/call"
  not input.mcp.tool_name in privileged_tools
}

allow if {
  input.mcp.method == "tools/call"
  input.mcp.tool_name in privileged_tools
  caller_in_approved_group
}

caller_in_approved_group if {
  some g in input.source_auth.claims.groups
  g in approved_groups
}

deny_reason := sprintf("Tool '%s' requires builder group membership", [input.mcp.tool_name]) if {
  input.mcp.method == "tools/call"
  input.mcp.tool_name in privileged_tools
  not caller_in_approved_group
}
```

**Sample input (ALLOW):**

```json
{
  "http": { "method": "POST", "path": "/v1/surfaces/my-surface/mcp", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "my-surface" },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "user@example.com",
    "claims": { "groups": ["11111111-2222-3333-4444-555555555555"] }
  },
  "mcp": { "method": "tools/call", "tool_name": "rotate_secret", "params": {} }
}
```

**Sample input (DENY)** - set `"groups": []`, or change the tool to a non-member
group ID.

---

### 8.9 Scenarios that need enrichment, not just the JWT

These are the scenarios from the same batch that cannot be written as a standalone
Rego sample, because the data they depend on is never present in `input` on its own.
To enforce them, fetch the signal out-of-band (Microsoft Graph, your agent
registry, a PIM check) and inject it via the surface's Metadata Injection element so
it lands in `input.metadata`, or populate `input.agent` via Trust Registry
extraction. Once that field exists in the input, the Rego is a one-line check.

| Scenario | Missing signal | Where it would need to come from |
| --- | --- | --- |
| Block disabled Entra ID users | `accountEnabled` | Graph API lookup -> `input.metadata.account_enabled` |
| Block inactive Entra ID users | `signInActivity.lastSignInDateTime` | Graph API lookup -> `input.metadata.last_sign_in` |
| Block orphaned agents | Agent owner mapping / validity | Agent registry or Trust Registry lookup -> `input.agent` |
| Secrets egress for scoped admins | Administrative-unit-scoped role assignment | Graph API role assignment lookup -> `input.metadata.scoped_roles` |
| User classification by custom security attributes | Custom security attributes | Graph API lookup -> `input.metadata.security_attributes` |
| Step-up by device compliance / sign-in risk | Conditional Access signals, device compliance | Conditional Access authentication context claim (`acrs`), or a device/risk lookup -> `input.metadata` |

Once the field is present, the pattern matches the rest of this guide, for example:

```rego
package surface.policy

import rego.v1

default allow := false

allow if {
  input.metadata.account_enabled == true
}

deny_reason := "Entra account is disabled" if {
  input.metadata.account_enabled == false
}

deny_reason := "No account status available - check Metadata Injection config" if {
  not input.metadata.account_enabled
}
```

---

## 9. Common Mistakes

| Mistake                                                                     | What happens                            | Fix                                                                                 |
| --------------------------------------------------------------------------- | --------------------------------------- | ----------------------------------------------------------------------------------- |
| Using `input.jwt.*` in a surface policy                                     | Always `undefined` -> silent deny       | Use `input.source_auth.claims.*`. `input.jwt` exists only in MCP per-tool policies. |
| Reading a bearer token from `input.http.headers.authorization`              | Header is stripped -> `undefined`       | Use `input.source_auth`.                                                            |
| `every r in results { r.ok }` with no count guard                           | Empty array returns `true` -> allow-all | Add `count(results) > 0`.                                                           |
| Checking `input.agent.trust_verification` without enabling trust extraction | `undefined` -> deny                     | Enable "Extract Trust Registry Data" on the surface.                                |
| Using `package channel.policy`                                              | Rejected on create/update               | Use `package surface.policy`.                                                       |
| `default allow := true`                                                     | Fails open                              | Always deny by default.                                                             |
| Checking `input.gateway.source_id` on an inbound direct call                | `null` on that path                     | Only use it on connection point or outbound legs.                                   |
| No `deny_reason`                                                            | Opaque 403s, hard to debug              | Add a `deny_reason` for each failure branch.                                        |
| Deleting a policy still attached to a surface                               | That surface fails **closed**           | Detach or replace before deleting.                                                  |

### Rego version note

Samples use `import rego.v1` (`if` / `in` / `every`). Omitting the import still
works where the gateway defaults to v1 syntax, but including it is explicit and
portable.

---

## 10. Learn More

- [OPA policies reference](https://docs.affinidi.com/products/affinidi-trust-fabric/agent-gateway/reference/surfaces/opa-policies/) - full `input` schema, dry-run panel, versioning, global enforcement.
- [OPA policies concepts](https://docs.affinidi.com/products/affinidi-trust-fabric/agent-gateway/concepts/opa-policies/) - evaluation order and policy scopes.
- [Apply OPA policies to your gateway and surfaces](https://docs.affinidi.com/products/affinidi-trust-fabric/agent-gateway/how-to-guides/policies/apply-opa-policies/)
- [Control MCP tool access with per-tool policies](https://docs.affinidi.com/products/affinidi-trust-fabric/agent-gateway/how-to-guides/policies/control-mcp-tool-access-with-per-tool-policies/)
- [Trust elements reference](https://docs.affinidi.com/products/affinidi-trust-fabric/agent-gateway/reference/surfaces/trust-element/) - Trust Check result fields and error codes.
- [Dashboard policy guide](../feature-guide/policy-guide.md) - step-by-step UI walkthrough.
- [Rego policy language](https://www.openpolicyagent.org/docs/latest/policy-language/)
