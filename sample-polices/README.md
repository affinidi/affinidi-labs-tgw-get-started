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
- [4. Policy Input Schema](#4-policy-input-schema)
  - [What `input` is](#what-input-is)
  - [Full schema](#full-schema)
  - [Namespace by namespace](#namespace-by-namespace)
  - [Presence by namespace](#presence-by-namespace)
  - [`input.source_auth` shapes](#inputsource_auth-shapes)
  - [Gateway-defined vs user-defined fields](#gateway-defined-vs-user-defined-fields)
  - [MCP per-tool policies use a different input](#mcp-per-tool-policies-use-a-different-input)
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

### The `deny_reason` rule

When a policy denies, the gateway evaluates a rule named exactly `deny_reason` and
surfaces its string in the dry-run result, the audit log, and the error response.
Always define one - it turns an opaque 403 into something your team can debug.

```rego
deny_reason := "Caller is not an admin" if {
  input.source_auth.claims.role != "admin"
}
```

> **`deny_reason` is only read on a deny.** The gateway evaluates it solely when
> `allow` is `false`; on an allow the reason is always empty. There is no
> `allow_reason` rule - the gateway never evaluates that name, so defining one has
> no effect.

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
**ALLOW** or **DENY** - without touching live traffic. On a **DENY** it also shows
your `deny_reason`; on an **ALLOW** no reason is shown.

Steps:

1. Open the policy in **Policies**.
2. Scroll to the **Test** panel.
3. Paste a sample input JSON (examples in every section below).
4. Click **Run against the draft above**.
5. Read the badge: **ALLOW** or **DENY**, plus `deny_reason` when the result is a
   deny and your policy defines one.

If the badge says _"Policy produced no `allow` decision"_, the Rego compiled but
the engine found no value at `data.<scope>.policy.allow` - the package declaration
is wrong for the scope, or there is no `default allow`.

Notes:

- The dry run evaluates the Rego **currently in the editor**, including unsaved
  changes. Nothing reaches the live policy engine.
- **Auto-run** re-evaluates shortly after every edit to the policy or the input.
- The button is disabled while the Rego does not compile or the JSON is invalid.
- The sample input is saved with the policy, so your last test input is still there
  next time.
- Draft size, input size, and run time are capped.

### Minimal starter input

Use this as the starting point for a surface policy. It carries the three
always-present namespaces plus a JWT caller:

```json
{
  "http": { "method": "POST", "path": "/", "headers": {} },
  "gateway": { "direction": "inbound" },
  "channel": { "config_id": "surface-abc123", "name": "My Surface" },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "user@example.com",
    "claims": { "sub": "user@example.com", "role": "admin" }
  }
}
```

For a gateway policy, drop `channel` and `source_auth` and keep `http` plus
`gateway`.

> **If the Test panel shows an input with a top-level `jwt` object, replace it.**
> Some policy editors start you off with a short placeholder like
> `{"jwt": {"sub": "...", "role": "admin"}, "http": {...}, "gateway": {...}}`. That
> is sample text, not a real request: the gateway never produces a top-level
> `input.jwt` for a gateway or surface policy. Claims arrive at
> `input.source_auth.claims`; `input.jwt` exists only in MCP per-tool policies.
>
> **The dry run does not validate your input against the schema.** It evaluates
> against whatever JSON you paste. A policy written around `input.jwt.role` will
> therefore return **ALLOW** in a dry run and then deny every real request, because
> that field is absent at runtime. A dry-run ALLOW only means something if the
> input you pasted matches the [schema above](#4-policy-input-schema).

### Suggested test matrix

For each policy, run at least three inputs:

| Case                   | Purpose                                     |
| ---------------------- | ------------------------------------------- |
| Happy path             | Confirms ALLOW when every condition is met. |
| One condition wrong    | Confirms DENY and the right `deny_reason`.  |
| Field missing entirely | Confirms the policy fails closed, not open. |

---

## 4. Policy Input Schema

### What `input` is

Before evaluating any Rego, the gateway serialises the request context into a
single JSON document and hands it to the policy engine as `input`. Your rules do
nothing but read fields off that document and return a boolean.

Two things follow from how it is built:

- **The schema is fixed.** `input` is a serialised Rust struct (`PolicyInput`), not
  an arbitrary bag. Top-level field names are exactly the thirteen listed below;
  anything else you reference does not exist.
- **Empty fields are omitted, not null.** Every optional field is skipped during
  serialisation when it has no value. In Rego a missing field is `undefined`, and
  any rule body containing an `undefined` expression simply does not fire - which,
  under `default allow := false`, is a silent deny.

### Full schema

A fully-populated `input` for an inbound A2A request. In practice you will never
see all of these at once - each namespace appears only under the conditions in the
[presence table](#presence-by-namespace).

```json
{
  "http": {
    "method": "POST",
    "path": "/a2a/tasks/send",
    "headers": { "content-type": "application/json" }
  },
  "gateway": {
    "direction": "inbound",
    "source_id": "did:web:example.com:agents:caller",
    "target_id": "fabric://.../96ab7082-5bb7-4a63-b881-cdc13abed1dd"
  },
  "channel": {
    "config_id": "10a0533d-b10b-4d02-a2fd-aaaaaaaad6e5",
    "name": "My Surface",
    "variant_alias": "staging"
  },
  "source_auth": {
    "method": "jwt_bearer",
    "subject": "user@example.com",
    "claims": { "scp": "agent.access", "tid": "0000...", "role": "admin" }
  },
  "a2a": {
    "method": "message/send",
    "message": { "role": "user", "kind": "message", "parts": [] }
  },
  "mcp": {
    "method": "tools/call",
    "tool_name": "search",
    "resource_uri": null,
    "prompt_name": null,
    "params": { "query": "hello" }
  },
  "agent": {
    "did": "did:web:example.com:agents:caller",
    "trust_verification": true,
    "source_trust_verification": true,
    "target_trust_verification": true,
    "agent_dna": { "uai": "urn:uai:..." },
    "trust_registry_did": "did:web:registry.example.com",
    "provider_did": "did:web:provider.example.com",
    "authority_did": "did:web:authority.example.com",
    "identity_issuer_did": "did:web:issuer.example.com",
    "tr_identity_mismatch": false
  },
  "trust_check_results": {
    "caller": [
      {
        "id": "tc-caller-1",
        "trust_registry_id": "fba52ad0-8e41-43fa-b5a8-64b2f92c4e57",
        "query_type": "recognition",
        "ok": true,
        "error": null,
        "name": "Verify caller",
        "authority_id": "did:web:authority.example.com",
        "entity_id": "did:web:example.com:agents:caller",
        "action": "is",
        "resource": "ownedAgent",
        "query_resolved": true
      }
    ],
    "target": []
  },
  "extension_identity": {
    "did": "did:web:example.com:agents:caller",
    "identity_hash": "sha256:..."
  },
  "identity_binding": {
    "verified": true,
    "agent": { "did": "did:web:gw1.example:agent", "identity_fields": {} },
    "caller": {
      "fields": { "sub": "user@example.com" },
      "user_hash": "adbff4cd...",
      "assurance": "gateway_attested",
      "identity_source": "transit_token"
    },
    "delegated": true,
    "issuer_gateway": "did:web:gw1.example",
    "target": "fabric://gw2/...",
    "intent": {}
  },
  "payment": { "verified": true, "response_header": "..." },
  "metadata": { "any_key": "any value" }
}
```

### Namespace by namespace

**`input.http`** - the raw HTTP envelope. `method` and `path` are strings;
`headers` is a flat string-to-string map with credential-bearing headers already
stripped (see [Stripped headers](#stripped-headers)). Use this for coarse
method/path gating.

**`input.gateway`** - which way the traffic is flowing and between whom.
`direction` is `"inbound"` (arriving at this gateway) or `"outbound"` (your
managed agent calling out through a transit point). `source_id` and `target_id`
carry DIDs or endpoint URLs and are populated only on the legs where they make
sense - both are omitted on a plain inbound call from an external client.

**`input.channel`** - which surface is handling the request. `config_id` is the
stable internal ID (survives renames, so prefer it in policies); `name` is the
display name; `variant_alias` appears only when the request URL selected a
non-default variant.

**`input.source_auth`** - who the caller is, as established by the Caller Context
element. A tagged union: `method` is the discriminant and decides which sibling
fields exist. This is the field most policies key on. Full shapes
[below](#inputsource_auth-shapes).

**`input.a2a`** - the agent message for A2A/AP2 traffic, captured from the
original request body _before_ the gateway injects identity. `method` is the
JSON-RPC method (e.g. `"message/send"`); `message` is the raw message object with
`role`, `parts`, `metadata`, `messageId`.

**`input.mcp`** - the MCP call on an inbound MCP request. `method` is the JSON-RPC
method (`"tools/call"`, `"tools/list"`, ...), with `tool_name`, `resource_uri`, or
`prompt_name` populated depending on which method it is, and `params` carrying the
full parsed params.

**`input.agent`** - resolved agent and trust-registry context, populated when
Trust Registry data extraction is enabled. `trust_verification` is `true` when all
recognition queries passed, `false` when any failed, and **absent when none ran** -
so `input.agent.trust_verification == true` denies on a surface where extraction is
off. `source_trust_verification` / `target_trust_verification` split the result per
leg in Both mode. `tr_identity_mismatch` is `true` when the trust-registry
extension's DID contradicts the identity extension's DID.

**`input.trust_check_results`** - per-leg outcomes of the Trust Check elements.
Present as soon as at least one element ran; when it exists, **both** `caller` and
`target` keys are present, and the leg that did not run on this seam is `[]` (so
rules never need null checks). Each entry carries `ok` (the field to gate on), the
element `id` and `name`, the resolved TRQP query (`authority_id`, `entity_id`,
`action`, `resource`), `query_type` (`"recognition"` or `"authorization"`),
`query_resolved` (false when template placeholders could not be substituted), and
`error` (`null` on success, otherwise `{ "code": ..., "message": ... }`).

**`input.extension_identity`** - the agent DID and a correlation hash taken from a
verified Verifiable Presentation in the request body.

**`input.identity_binding`** - a verified VP issued by an _upstream_ gateway,
proving who it was acting for. `caller.assurance` is `"gateway_attested"` or
`"caller_credential_chained"`; `delegated` says whether the sending gateway acted
on behalf of a user; `issuer_gateway` is the signing gateway's DID.

**`input.payment`** - set when an x402 payment was cryptographically verified.

**`input.metadata`** - a free-form key/value map populated by Metadata Injection
rules. The one place you can get external data into a policy.

### Presence by namespace

| Field                                                                            | Present when                                    | Notes                                                                                                                                                                                                     |
| -------------------------------------------------------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `input.http.method` / `.path` / `.headers`                                       | Always                                          | Sensitive headers are stripped.                                                                                                                                                                           |
| `input.gateway.direction`                                                        | Always                                          | `"inbound"` or `"outbound"`.                                                                                                                                                                              |
| `input.gateway.source_id`                                                        | Inbound via connection point, or outbound       | Caller DID, or managed agent DID on outbound. Omitted otherwise.                                                                                                                                          |
| `input.gateway.target_id`                                                        | Outbound / fabric send                          | Target URL or remote gateway DID.                                                                                                                                                                         |
| `input.channel.config_id` / `.name`                                              | Always                                          | Surface identity.                                                                                                                                                                                         |
| `input.channel.variant_alias`                                                    | Request used `/route$alias/...`                 | Omitted on the default variant.                                                                                                                                                                           |
| `input.source_auth.*`                                                            | Surface has a Caller Context element            | Shape depends on `method`. See below.                                                                                                                                                                     |
| `input.a2a.method` / `.message`                                                  | A2A / AP2 requests                              | Taken from the original body, before identity injection.                                                                                                                                                  |
| `input.mcp.method` / `.tool_name` / `.resource_uri` / `.prompt_name` / `.params` | Inbound MCP requests                            |                                                                                                                                                                                                           |
| `input.agent.*`                                                                  | Trust Registry data extraction enabled          | `did`, `trust_verification`, `source_trust_verification`, `target_trust_verification`, `agent_dna`, `trust_registry_did`, `provider_did`, `authority_did`, `identity_issuer_did`, `tr_identity_mismatch`. |
| `input.trust_check_results.caller` / `.target`                                   | At least one Trust Check element ran on the leg | Both keys always present when the object exists; the leg that did not run is `[]`.                                                                                                                        |
| `input.extension_identity.did` / `.identity_hash`                                | Verified VP in the request body                 |                                                                                                                                                                                                           |
| `input.payment.verified` / `.response_header`                                    | x402 payment verified                           |                                                                                                                                                                                                           |
| `input.identity_binding.*`                                                       | Verified VP from an upstream gateway            | `verified`, `agent.did`, `agent.identity_fields`, `caller.fields`, `caller.user_hash`, `caller.assurance`, `caller.identity_source`, `delegated`, `issuer_gateway`, `target`, `intent`.                   |
| `input.metadata.*`                                                               | Metadata Injection rules ran                    | Free-form key/value map.                                                                                                                                                                                  |

> **There is no `input.jwt` on a gateway or surface policy.** JWT claims arrive at
> `input.source_auth.claims`. `input.jwt` exists only in the separate MCP per-tool
> policy input - see [below](#gateway-defined-vs-user-defined-fields).

### `input.source_auth` shapes

The `method` field is the discriminant and determines which other fields exist:

```json
{ "method": "jwt_bearer", "subject": "user@example.com", "claims": { "role": "admin" } }
{ "method": "api_key",    "key_name": "my-client-id" }
{ "method": "did_auth",   "did": "did:web:example.com:caller" }
{ "method": "mtls",       "principal": "CN=svc,O=Example", "fingerprint": "sha256:...", "subject_dn": "CN=svc,O=Example", "issuer_dn": "CN=Example CA", "sans": {} }
{ "method": "failed",     "attempted_method": "jwt_bearer", "reason": "Token has expired" }
```

Notes:

- `input.source_auth` is **absent entirely** when the surface has no Caller Context
  element. A policy that reads `input.source_auth.anything` on such a surface is
  `undefined` and denies every request.
- It is also absent on the outbound leg - there is no caller to authenticate there.
- A failed authentication does **not** block the request on its own; the gateway
  hands `method: "failed"` to the policy layer and lets the policy decide. See
  [sample 5.2](#52-deny-when-caller-authentication-failed).
- On `mtls`, `principal`, `fingerprint`, `subject_dn`, and `issuer_dn` are always
  present; the `sans` sub-keys (`dns`, `uri`, `email`, `ip`) appear only when the
  certificate carries them.

### Gateway-defined vs user-defined fields

This distinction decides whether a field name is guaranteed or whether you have to
verify it yourself before writing a rule against it.

| Category                           | Fields                                                                                                                                                                   | Who controls the key names                                       |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| **Gateway-defined** (fixed schema) | `http`, `gateway`, `channel`, `source_auth.method`, `source_auth.subject`, `agent.*`, `trust_check_results.*`, `extension_identity.*`, `payment.*`, `identity_binding.*` | The gateway. Stable, exactly as listed above.                    |
| **User-defined** (free-form)       | **`source_auth.claims.*`**, `metadata.*`, `mcp.params.*`, `a2a.message.*`                                                                                                | Your IdP, your Metadata Injection config, or the calling client. |

The important one is **`input.source_auth.claims`**: the gateway copies the
validated token payload in verbatim and never normalises it. `role`, `scp`, `tid`,
`groups`, `wids`, `email`, `upn` and friends exist only if _your_ identity provider
emits them. Several are Entra ID optional claims that must be switched on in the
app registration first. Before shipping a claims-based policy:

1. Decode a real token from your IdP (or capture one in a dry run) and confirm the
   claim name and type - a scope can be a space-delimited string _or_ an array.
2. Use `object.get(input.source_auth, ["claims", "role"], "")` rather than a bare
   lookup so a missing claim produces your `deny_reason` instead of an
   `undefined` silent deny.

Similarly, `input.metadata` keys are whatever your Metadata Injection rules set,
and `input.a2a.message` / `input.mcp.params` are attacker-controllable request
body content - validate shape before trusting values.

### MCP per-tool policies use a different input

A policy bound to an individual MCP tool is evaluated against a separate struct,
not `PolicyInput`. Same package (`package surface.policy`), different fields:

| Surface / gateway policy           | MCP per-tool policy                              |
| ---------------------------------- | ------------------------------------------------ |
| `input.source_auth.claims.<claim>` | `input.jwt.<claim>` (flat claims map)            |
| `input.mcp.tool_name`              | `input.mcp.method` (tool name lives in `method`) |
| `input.http.method` / `.path`      | `input.request.method` / `.path`                 |
| `input.channel.config_id`          | `input.channel.id`                               |
| not available                      | `input.request.source_ip`                        |

How `input.jwt` is built:

- It is the **decoded payload of the `Bearer` token**, copied in as a flat map. So
  `input.jwt.sub`, `input.jwt.scp`, `input.jwt.role` are just the claims your token
  happens to carry - `role` is not a gateway-defined field, and it only exists if
  your IdP emits it. The same "verify against a real token" advice as
  [`source_auth.claims`](#gateway-defined-vs-user-defined-fields) applies.
- It is **omitted entirely** when there is no readable `Bearer` token on the
  request, so `input.jwt.anything` is `undefined` and denies.
- The claims are decoded, **not signature-verified, at this point**. Authenticity
  is established earlier by source authentication; `input.jwt` only surfaces the
  claims for the policy to read. Do not treat a per-tool policy as the thing
  proving the token is genuine - keep a Caller Context element doing that.
- `input.mcp.protocol` is always `"json-rpc-2.0"`.

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

**Expected:** `ALLOW` (no reason is shown on an allow).

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
> to an individual tool binding rather than the surface, the tool name is at
> `input.mcp.method`, claims are at `input.jwt.*`, and the path is at
> `input.request.path`. See
> [MCP per-tool policies use a different input](#mcp-per-tool-policies-use-a-different-input).

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
    "claims": {
      "scp": "agent.access",
      "tid": "00000000-f06b-4a99-85d8-ca5481d17d2e"
    }
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
> | Role                          | Template ID                            |
> | ----------------------------- | -------------------------------------- |
> | Global Administrator          | `62e90394-69f5-4237-9190-012177145e10` |
> | Privileged Role Administrator | `e8611ab8-c189-46e8-94e1-60213ab1f814` |
> | User Administrator            | `fe930be7-5e62-47db-91af-98c3a49a38b1` |
> | Application Administrator     | `9b895d92-2cd3-44c7-9d02-a6ac2d5ea5c3` |

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

| Scenario                                          | Missing signal                                | Where it would need to come from                                                                      |
| ------------------------------------------------- | --------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Block disabled Entra ID users                     | `accountEnabled`                              | Graph API lookup -> `input.metadata.account_enabled`                                                  |
| Block inactive Entra ID users                     | `signInActivity.lastSignInDateTime`           | Graph API lookup -> `input.metadata.last_sign_in`                                                     |
| Block orphaned agents                             | Agent owner mapping / validity                | Agent registry or Trust Registry lookup -> `input.agent`                                              |
| Secrets egress for scoped admins                  | Administrative-unit-scoped role assignment    | Graph API role assignment lookup -> `input.metadata.scoped_roles`                                     |
| User classification by custom security attributes | Custom security attributes                    | Graph API lookup -> `input.metadata.security_attributes`                                              |
| Step-up by device compliance / sign-in risk       | Conditional Access signals, device compliance | Conditional Access authentication context claim (`acrs`), or a device/risk lookup -> `input.metadata` |

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

| Mistake                                                                     | What happens                                                                          | Fix                                                                                 |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Using `input.jwt.*` in a surface policy                                     | Always `undefined` -> silent deny                                                     | Use `input.source_auth.claims.*`. `input.jwt` exists only in MCP per-tool policies. |
| Defining `allow_reason`                                                     | Nothing - the gateway never evaluates that rule                                       | Only `deny_reason` is read, and only when the decision is a deny.                   |
| Reading `input.source_auth` on a surface with no Caller Context element     | Field is absent -> `undefined` -> deny-all                                            | Add a Caller Context element, or do not branch on `source_auth`.                    |
| Reading `input.source_auth` on an outbound/target policy slot               | Never populated outbound                                                              | Use `input.gateway.target_id` or `input.trust_check_results.target`.                |
| Reading a bearer token from `input.http.headers.authorization`              | Header is stripped -> `undefined`                                                     | Use `input.source_auth`.                                                            |
| `every r in results { r.ok }` with no count guard                           | Empty array returns `true` -> allow-all                                               | Add `count(results) > 0`.                                                           |
| Assuming a claim like `role` or `groups` always exists                      | IdP-specific, often needs an Entra optional claim -> `undefined` -> deny              | Verify against a real token; wrap in `object.get(..., default)`.                    |
| Checking `input.agent.trust_verification` without enabling trust extraction | `undefined` -> deny                                                                   | Enable Trust Registry data extraction on the surface.                               |
| Using `package channel.policy`                                              | Rejected on create/update (legacy definitions were auto-migrated)                     | Use `package surface.policy`.                                                       |
| Omitting `default allow`                                                    | No value at `data.<scope>.policy.allow` -> fail closed with a misconfiguration reason | Always declare `default allow := false`.                                            |
| `default allow := true`                                                     | Fails open                                                                            | Always deny by default.                                                             |
| Checking `input.gateway.source_id` on an inbound direct call                | Field is omitted on that path                                                         | Only use it on connection point or outbound legs.                                   |
| No `deny_reason`                                                            | Opaque 403s, hard to debug                                                            | Add a `deny_reason` for each failure branch.                                        |
| Deleting a policy still attached to a surface                               | That surface fails **closed**                                                         | Detach or replace before deleting.                                                  |

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
