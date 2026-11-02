# Credential Providers Guide

## Overview

A **credential provider** tells Affinidi Agent Gateway how to obtain an OAuth access token from an identity provider (IdP). The gateway then attaches that token to the requests it forwards to a protected agent or API. Your agents never hold the client secret or private key: the gateway keeps that key material in **Secrets** and turns it into a short-lived token.

This guide covers the four OAuth provider types. Each one has its own step-by-step guide with IdP setup (portal and command line), gateway configuration, and a test.

| Guide                                                 | Provider type (dashboard label)                                   | Typical IdPs                                 |
| ----------------------------------------------------- | ----------------------------------------------------------------- | -------------------------------------------- |
| [Client Credentials](./client-credentials.md)         | OAuth 2.0, Client Credentials (2-legged, machine-to-machine)      | Keycloak, Microsoft Entra ID, Okta, Cognito  |
| [Authorization Code](./authorization-code.md)         | OAuth 2.0, Authorization Code (3-legged, user consent)            | Microsoft Entra ID, Google, Okta, Keycloak   |
| [JWT Bearer](./jwt-bearer.md)                         | OAuth 2.0, JWT Bearer (signed JWT grant)                          | Google Cloud (service accounts, Vertex AI)   |
| [Client Credentials JWT](./client-credentials-jwt.md) | OAuth 2.0, Client Credentials JWT (certificate, no client secret) | Microsoft Entra ID (Foundry), Okta, Keycloak |

The fifth type, **API Key (static secret)**, sends a stored key without any OAuth exchange. It is not covered here; see [Creating an API Key for a Surface](../surface-api-key.md) and [General Secret](../general-secret.md).

---

## How the Four Types Differ

| Type                   | `grant_type` sent to the IdP                  | How the gateway proves who it is                      | What you store in Secrets                          | User involved      |
| ---------------------- | --------------------------------------------- | ----------------------------------------------------- | -------------------------------------------------- | ------------------ |
| Client Credentials     | `client_credentials`                          | Client ID and client secret in the form body          | Client ID, client secret                           | No                 |
| Authorization Code     | `authorization_code` (with PKCE `S256`)       | Client ID and client secret, plus the user's approval | Client ID, client secret                           | Yes, once per user |
| JWT Bearer             | `urn:ietf:params:oauth:grant-type:jwt-bearer` | A JWT signed with a private key **is** the grant      | Private key (PEM)                                  | No                 |
| Client Credentials JWT | `client_credentials`                          | A JWT signed with a private key replaces the secret   | Client ID, private key (PEM), optional certificate | No                 |

The two JWT types look similar but follow different parts of [RFC 7523](https://www.rfc-editor.org/rfc/rfc7523):

- **JWT Bearer** (RFC 7523 §2.1). The signed JWT *is* the authorization grant. It names the identity in `iss`, carries the requested scopes in its own `scope` claim, and is sent with no client ID. Google service accounts work this way.
- **Client Credentials JWT** (RFC 7523 §2.2, `private_key_jwt`). A normal client credentials request in which a signed JWT (`client_assertion`) authenticates the client instead of a secret. `iss` and `sub` are the client ID, and scopes go in the form body. Entra certificate credentials, Okta and Keycloak work this way.

---

## Which One Should I Use?

```text
Does the downstream API act on behalf of a specific end user?
├── Yes ─► Authorization Code (each user consents once; delegation only)
└── No, the gateway calls as a service
    ├── Google Cloud (Vertex AI, Google APIs) with a service account?
    │   └── Yes ─► JWT Bearer
    ├── Can the IdP authenticate the client with a certificate or key pair?
    │   └── Yes ─► Client Credentials JWT  (preferred: no shared secret)
    └── Otherwise ─► Client Credentials (client secret)
```

Prefer a key pair over a shared secret where the IdP supports it. The private key never leaves the gateway, each signed assertion lives five minutes, and you can generate the key pair yourself and upload only the public half to the IdP.

---

## Identity Provider Support

| IdP                                    | Client Credentials | Authorization Code | JWT Bearer | Client Credentials JWT |
| -------------------------------------- | :----------------: | :----------------: | :--------: | :--------------------: |
| Microsoft Entra ID                     |         ✅         |         ✅         |    ❌ ¹    |          ✅ ²          |
| Google Cloud                           |        ❌ ³        |         ✅         |     ✅     |          ❌ ³          |
| Okta                                   |        ✅ ⁴        |         ✅         |    ❌ ⁵    |           ✅           |
| Keycloak                               |         ✅         |         ✅         |    ❌ ⁵    |           ✅           |
| Auth0                                  |        ⚠️ ⁶        |         ✅         |     ❌     |          ⚠️ ⁶          |
| Amazon Cognito                         |         ✅         |         ✅         |     ❌     |          ❌ ⁷          |
| Ping Identity (PingOne / PingFederate) |         ✅         |         ✅         |    ⚠️ ⁸    |           ✅           |
| Ory (Hydra / Ory Network)              |         ✅         |         ✅         |    ⚠️ ⁸    |          ✅ ²          |

✅ supported ⚠️ supported with conditions ❌ not offered by the IdP for this flow, or not compatible with how the gateway sends it

1. Entra's `jwt-bearer` grant is the On-Behalf-Of flow. It needs client authentication and an incoming user token, so it is not a gateway JWT Bearer flow. Use Client Credentials JWT with a certificate instead.
2. Entra finds the key by certificate thumbprint, so also store the certificate (the gateway then sends an `x5t#S256` header). Ory and most other IdPs find the key by `kid`.
3. Google's token endpoint has no client credentials grant. Use a service account with JWT Bearer.
4. Use a custom authorization server for client secret clients. Okta's own management scopes (`okta.*`) require `private_key_jwt`.
5. Okta (Cross App Access) and Keycloak (JWT Authorization Grant) implement RFC 7523 §2.1, but both also require the client to authenticate. The gateway's JWT Bearer request carries no client authentication, so use Client Credentials JWT with these IdPs.
6. Auth0 needs an `audience` for machine-to-machine tokens, and the gateway does not send one. Set the tenant's **Default Audience** (Settings → API Authorization Settings) to your API identifier.
7. Cognito's token endpoint accepts only `client_secret_basic` and `client_secret_post`.
8. Offered by the IdP in some configurations. Confirm the grant is accepted without client authentication before relying on it.

---

## Where a Provider Is Used

A provider on its own does nothing. You reference it from a surface in one of two places.

### 1. Target Authentication: the gateway authenticates as itself

Use this for the **Managed Agent** behind an Access Point, or for a **Transit Point** upstream. Every forwarded request gets the same service token, whoever the caller is.

In the Surface Builder, open the Managed Agent (or Transit Point) and fill in **Target Authentication**:

| Field               | Value                                   |
| ------------------- | --------------------------------------- |
| Credential Source   | Credential provider                     |
| Credential Provider | your provider                           |
| Authentication Type | Bearer                                  |
| Header Name         | `Authorization`                         |
| Header Format       | `Bearer {value}`                        |
| Fallback Behavior   | Reject request (502 Bad Gateway)        |

The surface stores this as:

```json
"auth": {
  "method": {
    "credential_provider": {
      "provider_id": "<credential-provider-id>",
      "header_name": "Authorization",
      "header_format": "Bearer {value}",
      "scopes": ["<optional, overrides the provider's Default Scopes>"]
    }
  },
  "auth_type": "bearer",
  "fallback": "reject"
}
```

Any OAuth type except Authorization Code can be used here, because there is no user to consent.

### 2. Credential Delegation: the gateway injects a credential into an agent's outbound calls

Add a **Credential Delegation** element to the surface and add a binding (`outbound_credentials`):

| Field               | Options                                                                  |
| ------------------- | ------------------------------------------------------------------------ |
| Credential Provider | your provider                                                            |
| Consent Mode        | On demand (signal `consent_required`), Pre-authorize, Elicit (MCP)       |
| Required For        | All outbound requests, or specific MCP tools only                        |
| Inject As           | Bearer header, Custom header (format uses `{value}`), or JSON-RPC `_meta` |
| Scopes              | optional override of the provider's Default Scopes                       |

Delegation stores tokens per caller and per agent. It therefore needs an authenticated caller on the Access Point and an agent identity on the surface. Without a caller identity the request is refused with `403 identity-required`. Consent Mode only matters for Authorization Code providers; the other types get a token without a user.

Further reading: [Credentials concept](https://docs.affinidi.com/products/affinidi-trust-fabric/agent-gateway/concepts/credentials/), [Configure per-caller credential delegation](https://docs.affinidi.com/products/affinidi-trust-fabric/agent-gateway/how-to-guides/setup/configure-per-caller-credential-delegation/), [Managed Agent reference](https://docs.affinidi.com/products/affinidi-trust-fabric/agent-gateway/reference/surfaces/managed-agent/).

---

## Shared Rules

These apply to every OAuth provider type.

**Secrets, not values.** Provider fields such as **Client ID Secret**, **Client Secret**, **Signing Key** and **Certificate** reference entries in **Secrets**. Create the secrets first (**Secrets → New Secret**, type `General`), then select them in the provider form. The provider API never returns key material.

**Key formats.** Signing keys must be PEM: PKCS#1 (`BEGIN RSA PRIVATE KEY`) or PKCS#8 (`BEGIN PRIVATE KEY`) for RSA, PKCS#8 for EC. Certificates must be PEM (`BEGIN CERTIFICATE`). The gateway checks the key on save, so a wrong format fails the save rather than the first request.

**Scopes must match exactly.** When scopes are requested, the `scope` returned by the IdP must be exactly the same set, no more and no fewer, or the token is refused. Some IdPs add default scopes to every token (for example Keycloak's `profile email`). Remove those defaults from the client, or leave **Default Scopes** empty to accept whatever the IdP issues. When the IdP returns no `scope` field, the requested scopes are assumed.

**Caching.** A token is cached until 60 seconds before it expires. The IdP response must include `expires_in`, a non-empty `access_token`, and `token_type: Bearer`. Editing the provider invalidates its cached tokens. A `401` from the downstream agent does **not** evict the cached token. After changing permissions at the IdP, save the provider again or wait for the token to expire.

**Token endpoint.** Use the tenant- or realm-specific endpoint (for Entra, never `common`). For Entra v2.0, express the audience as `<resource>/.default` in the scopes, not as a `resource` parameter.

**Inspecting tokens.** **Credentials → Credential Tokens** lists every token the gateway holds, including Target Authentication tokens. **Credentials → Credential Delegation Audit** records lookups, consents, refreshes and injections.

**Calling an A2A surface.** A2A requests through the gateway use protocol version 1.0. Send the header `A2A-Version: 1.0`; without it the gateway assumes `0.3` and answers `Unsupported A2A protocol version`.

---

## Current Limitations

- Only OAuth **access tokens** are obtained. OIDC **ID tokens** with a custom audience (for example, for Google Cloud Run or Cloud Functions IAM) are not supported.
- Keyless options are not available: no Google service account impersonation, workload identity federation, or managed identity. The JWT types need a private key stored in Secrets.
- The Surface Builder's MCP tool discovery accepts only a static secret for target authentication.
- Authorization Code cannot be used for Target Authentication.

---

## Related Guides

- [General Secret](../general-secret.md): storing values in Secrets
- [Creating an API Key for a Surface](../surface-api-key.md): the caller authentication used in the test calls
- [JWT Strategy Guide](../jwt-strategy-guide.md): authenticating callers with a JWT, for per-user delegation
- [Gateway Guide](../gateway-guide.md)
