# MCP Lab (Latest Protocol — Streamable HTTP, 2026-07-28)

This lab mirrors [`../mcp`](../mcp) but upgrades the server/client to the
**latest MCP spec transport** supported by the Agent Gateway. Full spec:
[modelcontextprotocol.io/specification/2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28)
(Streamable HTTP transport: [.../basic/transports/streamable-http](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http),
versioning: [.../basic/versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning)).

> **Note:** `2026-07-28` is a major revision. It removes the `initialize`
> handshake and protocol-level sessions entirely (both introduced in
> `2025-03-26`/`2025-06-18`). Every request is now stateless and self-describing.

## Table of contents

- [Protocol comparison](#protocol-comparison)
- [Run locally](#run-locally)
- [Route through the Agent Gateway](#route-through-the-agent-gateway)
- [Supported methods](#supported-methods)
- [Sample requests and responses](#sample-requests-and-responses)
  - [Discover the server](#discover-the-server)
  - [List tools](#list-tools)
  - [Call a tool](#call-a-tool)
- [Notes](#notes)

## Protocol comparison

|                       | `2025-06-18` (previous revision)                                                                  | `2026-07-28` (this lab)                                                                                                                                                          |
| --------------------- | ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Transport             | Streamable HTTP on `/mcp` (`POST`/`GET`/`DELETE`)                                                 | Streamable HTTP on `/mcp` (`POST` only); each request receives JSON or a request-scoped SSE stream                                                                               |
| Handshake             | `initialize` request, acknowledged with `notifications/initialized`                               | None — `initialize` was removed; servers **MUST** implement `server/discover` instead                                                                                            |
| Sessions              | `Mcp-Session-Id` issued on `initialize`, required on every subsequent call, closable via `DELETE` | None — `Mcp-Session-Id` / `GET` stream / `DELETE` were all removed; every request is independent                                                                                 |
| Version declaration   | Negotiated once at `initialize`, then just an `MCP-Protocol-Version` header                       | Per-request: `params._meta["io.modelcontextprotocol/protocolVersion"]`, mirrored in the `MCP-Protocol-Version` header                                                            |
| Request metadata      | Client identity and capabilities established during `initialize`                                  | Every request requires `_meta` fields `io.modelcontextprotocol/protocolVersion` and `io.modelcontextprotocol/clientCapabilities`; `clientInfo` is recommended                    |
| Method/name mirroring | None                                                                                              | `Mcp-Method` mirrors every `method`; `Mcp-Name` mirrors `params.name` or `params.uri` for `tools/call`, `resources/read`, and `prompts/get`; mismatches return `-32020`          |
| Batch requests        | Removed (vs. `2024-11-05`)                                                                        | Still not part of this transport                                                                                                                                                 |
| Result discriminator  | `resultType` absent; clients treat it as `"complete"`                                             | Every successful result requires `resultType`: `"complete"` for a final result or `"input_required"` when more input is needed; advertised extensions may define other values    |
| Cache metadata        | Not required                                                                                      | Complete results from discover, list, and resource-read operations require `ttlMs >= 0` and `cacheScope` (`"public"` or `"private"`); `input_required` results are not cacheable |
| Notifications         | Standalone `GET` SSE stream and server-to-client requests                                         | Request-scoped notifications use the request's SSE response; change notifications use `subscriptions/listen`; server interactions use `input_required` results                   |
| Tool output           | `content` required; `structuredContent` optional                                                  | `content` required; `structuredContent` optional; when a tool declares `outputSchema`, structured output must conform to it                                                      |
| Errors                | Generic JSON-RPC errors                                                                           | `-32020 HeaderMismatch`, `-32021 MissingRequiredClientCapability`, and `-32022 UnsupportedProtocolVersion`                                                                       |

## Run locally

```bash
cd mcp-latest
./run.sh
```

Follow the prompt to expose the server (ngrok, an existing public URL, or
localhost-only), then test it directly:

```bash
./test.sh http://localhost:11100
```

## Route through the Agent Gateway

Follow the same steps as [MCP Server via Agent Gateway](../README.md#mcp-server-via-agent-gateway)
in the main README, with one difference: point the **Managed Agent Endpoint URL**
at `<public-url>/mcp` (not the bare root), since this server's single Streamable
HTTP endpoint lives at `/mcp`.

Then test via the gateway route:

```bash
./test.sh https://<GATEWAY_HOST>/routes/<CHANNEL_PATH>
```

## Supported methods

This lab advertises only the `tools` capability and intentionally implements
the three methods exercised by its client:

| Method                                                         | Status          | Purpose                                                                                   |
| -------------------------------------------------------------- | --------------- | ----------------------------------------------------------------------------------------- |
| `server/discover`                                              | Implemented     | Returns supported protocol versions, capabilities, server information, and cache metadata |
| `tools/list`                                                   | Implemented     | Returns the available calculator and weather tools                                        |
| `tools/call`                                                   | Implemented     | Invokes a named tool with validated arguments                                             |
| `prompts/list`, `prompts/get`                                  | Not implemented | Prompt discovery and retrieval require the `prompts` capability                           |
| `resources/list`, `resources/templates/list`, `resources/read` | Not implemented | Resource discovery and reading require the `resources` capability                         |
| `completion/complete`                                          | Not implemented | Provides argument or reference autocompletion                                             |
| `subscriptions/listen`                                         | Not implemented | Opens an SSE stream for requested change notifications                                    |

Requests for unimplemented methods return JSON-RPC `-32601 Method not found`.
They are not missing from the test suite because the server does not advertise
their corresponding capabilities.

## Sample requests and responses

These examples call the local `/mcp` endpoint. For an Agent Gateway route,
replace `http://localhost:11100` with the gateway route URL.

### Discover the server

`server/discover` replaces the legacy `initialize` handshake and returns the
versions and capabilities supported by the server.

```bash
curl -sS http://localhost:11100/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: server/discover' \
  --data '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "server/discover",
    "params": {
      "_meta": {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientInfo": {
          "name": "curl-example",
          "version": "1.0.0"
        },
        "io.modelcontextprotocol/clientCapabilities": {}
      }
    }
  }'
```

Response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "resultType": "complete",
    "supportedVersions": ["2026-07-28"],
    "capabilities": {
      "tools": {}
    },
    "_meta": {
      "io.modelcontextprotocol/serverInfo": {
        "name": "Streamable HTTP MCP Server",
        "version": "3.0.0"
      }
    },
    "instructions": "This server provides a calculator and a weather forecast tool.",
    "ttlMs": 3600000,
    "cacheScope": "public"
  }
}
```

### List tools

The `Mcp-Method` and `MCP-Protocol-Version` headers must match the request body.

```bash
curl -sS http://localhost:11100/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/list' \
  --data '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {
      "_meta": {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientInfo": {
          "name": "curl-example",
          "version": "1.0.0"
        },
        "io.modelcontextprotocol/clientCapabilities": {}
      }
    }
  }'
```

Representative response (the server returns both tools):

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "resultType": "complete",
    "tools": [
      {
        "name": "calculator",
        "description": "Perform basic arithmetic calculations",
        "inputSchema": {
          "type": "object",
          "properties": {
            "operation": { "type": "string" },
            "a": { "type": "number" },
            "b": { "type": "number" }
          },
          "required": ["operation", "a", "b"]
        }
      }
    ],
    "ttlMs": 300000,
    "cacheScope": "public"
  }
}
```

### Call a tool

`tools/call` additionally requires `Mcp-Name` to match `params.name`.

```bash
curl -sS http://localhost:11100/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/call' \
  -H 'Mcp-Name: calculator' \
  --data '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "calculator",
      "arguments": {
        "operation": "add",
        "a": 15,
        "b": 27
      },
      "_meta": {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientInfo": {
          "name": "curl-example",
          "version": "1.0.0"
        },
        "io.modelcontextprotocol/clientCapabilities": {}
      }
    }
  }'
```

Response:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Calculation: 15 + 27 = 42"
      }
    ],
    "structuredContent": {
      "operation": "add",
      "a": 15,
      "b": 27,
      "result": 42
    },
    "resultType": "complete"
  }
}
```

## Notes

- `GET /mcp` and `DELETE /mcp` both return `405` — this revision removed the
  GET stream endpoint and protocol-level sessions, so only `POST` is valid.
- Every request is stateless: there's nothing to "connect" or "close" — the
  test client just sends `server/discover`, `tools/list`, and `tools/call`
  independently, each carrying its own protocol version/method/name metadata.
- The test suite also exercises two spec-defined error paths: an unsupported
  protocol version (`-32022`) and a mismatched `Mcp-Method` header (`-32020`).
- Origin validation and target-auth/OPA policy guides from `../mcp` apply
  unchanged — see [`../mcp/enable-auth.md`](../mcp/enable-auth.md) and
  [`../mcp/policies.md`](../mcp/policies.md).
