# Applying OPA Policies in the Agent Gateway (Optional)

> **Audience:** Customers who have already set up a surface in the Agent Gateway and want to enforce fine-grained access control using Open Policy Agent (OPA) policies.
>
> **Status:** These steps are **optional**. Use them when you need to:
>
> - Apply a **gateway-wide** rule that governs all inbound/outbound traffic across every surface (**Gateway Policy**), and / or
> - Apply a **per-surface** rule that controls traffic for a specific surface (**Surface Policy**).

---

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Overview](#overview)
- [Part A — Create a Policy](#part-a--create-a-policy)
- [Part B — Apply a Gateway-Level Policy](#part-b--apply-a-gateway-level-policy)
- [Part C — Apply a Surface-Level Policy](#part-c--apply-a-surface-level-policy)
- [Policy Reference](#policy-reference)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

- An MCP or A2A surface already created in the Agent Gateway.
- Access to the Agent Gateway dashboard with permission to manage **Policies**.
- Basic familiarity with [Rego](https://www.openpolicyagent.org/docs/latest/policy-language/) (the OPA policy language).

---

## Overview

The Agent Gateway evaluates OPA policies on every request before forwarding it upstream. Policies are written in Rego and have access to JWT claims, HTTP context, and routing information.

```
  Inbound Request
       │
       ▼
  ┌─────────────────────────────────────┐
  │         Agent Gateway               │
  │                                     │
  │  1. Gateway Policy (optional)       │  ◄── applies to ALL surfaces
  │  2. Surface Policy (optional)       │  ◄── applies to ONE surface
  │                                     │
  └─────────────────────────────────────┘
       │  allow = true
       ▼
  Upstream Server
```

| Scope              | Where configured                      | Applies to           |
| ------------------ | ------------------------------------- | -------------------- |
| **Gateway Policy** | Policies page → Gateway tab           | All surfaces         |
| **Surface Policy** | Policies page → Agent Surfaces tab    | One specific surface |

Both scopes use the same policy definition — the difference is only where the policy is attached.

---

## Part A — Create a Policy

All policies are managed from the **Policies** page before being attached to a gateway or surface.

### A.1 — Open the Policies Page

1. In the Agent Gateway dashboard, navigate to **Policies**.
2. The page has three tabs: **Gateway**, **Agent Surfaces**, and **Paywall**.

![Policies page — Gateway tab](docs/policy/policy-page-gateway.jpg)

### A.2 — Define a Gateway Policy

1. On the **Gateway** tab, click **`+ Define Gateway Policy`**.
2. Fill in the form:
   - **Name:** a short, descriptive identifier (e.g. `allow-only-your-company`)
   - **Type:** `Gateway`
   - **Description:** _(optional)_
   - **Policy Content (Rego):** paste your Rego policy (see [Policy Reference](#policy-reference) below)
3. Click **Save**.

![Create gateway policy form](docs/policy/policy-create-gateway.jpg)

A gateway-level policy applies to **all** traffic passing through the gateway, regardless of surface.

The new policy appears in the list with **Status: Enabled**.

### A.3 — Define a Surface Policy

1. Switch to the **Agent Surfaces** tab.
2. Click **`+ Define Agent Surface Policy`**.

![Policies page — Agent Surfaces tab](docs/policy/policy-page-agent-surfaces.jpg)

3. Fill in the form:
   - **Name:** a short, descriptive identifier (e.g. `allow-only-sub`)
   - **Type:** `Agent Surfaces`
   - **Description:** _(optional)_
   - **Policy Content (Rego):** paste your Rego policy — surface policies use `package surface.policy`
4. Click **Create**.

![Create surface policy form](docs/policy/policy-create-surface.jpg)

The saved policy appears with its system-assigned **Policy ID** and **Status: Enabled**.

![Saved surface policy](docs/policy/policy-edit-surface.jpg)

---

## Part B — Apply a Gateway-Level Policy

A gateway-level policy is automatically applied to **all** surfaces once it is defined and enabled on the **Gateway** tab. No additional attachment step is required — the gateway evaluates it on every inbound and outbound request.

To disable or swap the gateway policy, return to **Policies → Gateway** and edit or delete the policy.

---

## Part C — Apply a Surface-Level Policy

A surface-level policy applies only to traffic on a specific surface, allowing different rules per surface.

### C.1 — Attach the Policy to a Surface

1. In the Agent Gateway dashboard, open **Surfaces** and select the surface you want to protect.
2. In the **Palette**, search for **Policy** under **Security & Policy**.
3. Drag and drop the **Policy** element onto the canvas between the **Access Point** and the **Managed Agent**.
4. In the **Policy** configuration panel that opens on the right, select the policy you created in Part A.3 from the **Policy Definition** dropdown.
5. Click **Save**.

![Surface canvas — Policy element attached](docs/policy/policy-surface-canvas.jpg)

Requests to this surface will now be evaluated against the selected policy. Other surfaces are unaffected.

---

## Policy Reference

### Policy Structure

Gateway policies use the `gateway.policy` package; surface policies use the `surface.policy` package. Both define an `allow` rule:

```rego
package gateway.policy   # or: package surface.policy

# Default decision (true = allow all, false = deny all)
default allow = false

# Rules that evaluate to true allow the request
allow if {
  # Your conditions here
}
```

> **Best Practice:** Always start with `default allow = false` and explicitly allow only what you need.

### Available Input Context

| Variable                  | Description                       |
| ------------------------- | --------------------------------- |
| `input.jwt.*`             | JWT claims (e.g. `sub`, `role`)   |
| `input.http.method`       | HTTP method (`GET`, `POST`, etc.) |
| `input.http.path`         | Request path                      |
| `input.http.headers`      | HTTP request headers              |
| `input.gateway.direction` | `"inbound"` or `"outbound"`       |
| `input.channel.config_id` | Target channel config ID          |
| `input.channel.name`      | Target channel name               |

### Example: Require Authentication

Only allow requests that carry a valid JWT with a `sub` claim:

```rego
package gateway.policy

default allow = false

allow if {
  input.jwt.sub
}
```

### Example: Admin-Only Access

Restrict access to users whose JWT `role` claim equals `"admin"`:

```rego
package gateway.policy

default allow = false

allow if {
  input.jwt.role == "admin"
}
```

### Example: Allow Specific HTTP Methods Only

Block everything except `POST` requests:

```rego
package gateway.policy

default allow = false

allow if {
  input.http.method == "POST"
}
```

### Example: Scope by Channel Name

Apply different logic based on which channel is being called (useful in a gateway-level policy):

```rego
package gateway.policy

default allow = false

# Public channel — open to all
allow if {
  input.channel.name == "public-mcp"
}

# Private channel — require authentication
allow if {
  input.channel.name == "private-mcp"
  input.jwt.sub
}
```

---

## Troubleshooting

| Symptom                                           | Likely cause                                                                 | Fix                                                                                                      |
| ------------------------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `403 Forbidden` on all requests                   | Policy evaluates to `allow = false` for every request.                       | Review your Rego rules; verify the input fields you reference (e.g. `input.jwt.sub`) are present.        |
| Policy changes have no effect                     | The policy is not attached, or the wrong policy is selected.                 | Re-check the **Gateway** or **Agent Surfaces** tab and confirm the correct policy is selected and saved. |
| `403` only on some surfaces                       | A surface-level policy is overriding or conflicting with the gateway policy. | Review both the gateway-level and surface-level policy for that surface.                                 |
| JWT claims not available (`input.jwt.*` is empty) | The request does not carry a JWT, or the caller context is not configured.   | Ensure the surface's Access Point has a JWT verification strategy configured, or ensure the client sends a valid Bearer token. |
| Rego syntax error on save                         | Invalid Rego syntax in the Policy Content field.                             | Use the [OPA Playground](https://play.openpolicyagent.org/) to validate your policy before pasting.      |

---

## Next Steps

- Combine policies with [Source / Target Authentication](enable-auth.md) for layered security.
- Back to the [main README](../README.md).
