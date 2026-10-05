# A2A v1.0.1 Lab

This lab is a minimal A2A v1.0 echo agent for validating an Agent Gateway A2A v1.0.1 surface. It intentionally has its own virtual environment and pins `a2a-sdk[http-server]==1.0.1`; it does not change the legacy `a2a/` v0.3 lab. Its card and agent responses advertise the `https://fabric.affinidi.io/extensions/agent-identity/v1` extension with the agent name, model, and role. The interactive client also sends optional caller identity metadata using that extension.

> **Important: send and forward `A2A-Version: 1.0`.** A2A interprets a missing or empty `A2A-Version` request header as protocol version `0.3`. A v1-only agent will then reject the request with a version-compatibility error. When using an Agent Gateway, configure the route to preserve this header when forwarding the request to the target agent.

## A2A v0.3 and v1.0

`a2a-sdk==1.0.1` is the Python SDK release used by this lab. The A2A protocol version advertised in the card and sent in `A2A-Version` remains `1.0`.

| Concern             | A2A v0.3                                                     | A2A v1.0                                                                                |
| ------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| Version negotiation | No `A2A-Version` header, or `A2A-Version: 0.3`               | `A2A-Version: 1.0` is required                                                          |
| Agent-card endpoint | Top-level `url`, `protocolVersion`, and `preferredTransport` | `supportedInterfaces[]` entries contain `url`, `protocolBinding`, and `protocolVersion` |
| JSON-RPC method     | Slash form, for example `message/send`                       | PascalCase SDK method, for example `SendMessage`                                        |
| Roles and parts     | Role such as `user`; text part uses `kind: text`             | Role such as `ROLE_USER`; text part is a protobuf JSON object with `text`               |
| Task state          | Lowercase, for example `completed`                           | Enum form, for example `TASK_STATE_COMPLETED`                                           |
| Compatibility       | Native v0.3 SDK or a v1 compatibility adapter                | Native v1 SDK; a missing version header falls back to v0.3                              |

> **Gateway limitation:** Agent Gateway does not currently support A2A streaming. This lab advertises `streaming: false` and uses JSON-RPC `SendMessage`, which returns one completed task. Do not enable `SendStreamingMessage` until gateway streaming support is available.

References:

- [A2A protocol specification](https://a2a-protocol.org/latest/specification/)

## Run the agent

```bash
cd a2a-v1
./run.sh
```

The local server listens on port `10001`. Starting the lab again stops any process that is already listening on that port. To publish a different agent-card URL when running behind a tunnel or a gateway target, set `PUBLIC_BASE_URL` before starting it:

```bash
PUBLIC_BASE_URL=https://example-tunnel.example ./run.sh 10001
```

Configure the Agent Gateway A2A surface target to the public base URL. The published card is available at `/.well-known/agent-card.json`, and declares `supportedInterfaces` with `protocolBinding: JSONRPC` and `protocolVersion: 1.0`.

## Test a route

### Test locally

With the agent running, use a second terminal to verify the local agent first:

```bash
cd a2a-v1
./test.sh http://localhost:10001
```

`test.sh` fetches and displays the agent card, then opens an interactive prompt for sending messages. For an automated card-discovery, identity-extension, and message round-trip check, run:

```bash
./smoke_test.sh http://localhost:10001
```

### Test through Agent Gateway

1. Expose the local agent at a public URL, then restart it with that URL in `PUBLIC_BASE_URL`. The agent card must advertise the public URL rather than `localhost`.
2. In Agent Gateway, create an **A2A surface** and select **Managed Agent**.
3. Set the managed agent's target URL to the public base URL of this agent.
4. Create the surface, copy its Gateway **Access Point** URL, and use it as the client target:

```bash
./test.sh https://your-gateway-access-point.example
```

Use the automated check against the same Access Point when needed:

```bash
./smoke_test.sh https://your-gateway-access-point.example
```
