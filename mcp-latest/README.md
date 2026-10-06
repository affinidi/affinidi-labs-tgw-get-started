# MCP Lab (Latest Protocol — Streamable HTTP, 2026-07-28)

This lab mirrors [`../mcp`](../mcp) but upgrades the server/client to the
**latest MCP spec transport** supported by the Agent Gateway. Full spec:
[modelcontextprotocol.io/specification/2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28)
(Streamable HTTP transport: [.../basic/transports/streamable-http](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http),
versioning: [.../basic/versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning)).

> **Note:** `2026-07-28` is a major revision. It removes the `initialize`
> handshake and protocol-level sessions entirely (both introduced in
> `2025-03-26`/`2025-06-18`). Every request is now stateless and self-describing.

|                       | `2025-06-18` (previous revision)                                                                  | `2026-07-28` (this lab)                                                                                                              |
| --------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Transport             | Streamable HTTP on `/mcp` (`POST`/`GET`/`DELETE`)                                                 | Streamable HTTP on `/mcp` (`POST` only)                                                                                              |
| Handshake             | `initialize` request, acknowledged with `notifications/initialized`                               | None — `initialize` was removed; servers **MUST** implement `server/discover` instead                                                |
| Sessions              | `Mcp-Session-Id` issued on `initialize`, required on every subsequent call, closable via `DELETE` | None — `Mcp-Session-Id` / `GET` stream / `DELETE` were all removed; every request is independent                                     |
| Version declaration   | Negotiated once at `initialize`, then just an `MCP-Protocol-Version` header                       | Per-request: `params._meta["io.modelcontextprotocol/protocolVersion"]`, mirrored in the `MCP-Protocol-Version` header                |
| Method/name mirroring | None                                                                                              | `Mcp-Method` header mirrors `method`; `Mcp-Name` header mirrors `params.name` on `tools/call` (required, validated against the body) |
| Batch requests        | Removed (vs. `2024-11-05`)                                                                        | Still not part of this transport                                                                                                     |
| Tool output           | `content` **and** `structuredContent`                                                             | `content` **and** `structuredContent` (+ `outputSchema` on tools)                                                                    |
| Errors                | Generic JSON-RPC errors                                                                           | Structured: `-32022 UnsupportedProtocolVersionError`, `-32020 HeaderMismatch`                                                        |

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
