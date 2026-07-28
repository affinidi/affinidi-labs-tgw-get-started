# Chat MCP Server

The MCP server for the `auth0-mcp-surface` chat demo. It exposes a single
**`chat`** tool over JSON-RPC (`POST /`, port **9740**) and is the upstream the
chat surface talks to **through the Agent Gateway**.

- **`chat`** answers via **AWS Bedrock** when configured (`BEDROCK_MODEL_ID` +
  AWS credentials, see [.env.example](.env.example)); otherwise it returns a
  **stub** reply — so getting-started works with no LLM.
- The LLM is _your_ infrastructure. Credential delegation at the gateway scopes
  _who_ can call this / what data it may reach — it does not borrow the user's
  own LLM account.

## Run

```bash
./run.sh                      # venv + deps + serve on :9740
# or, from the repo root:
make mcp
```

## Wire into the Agent Gateway

1. Expose this server publicly (your proxy, or `ngrok http 9740`).
2. Gateway dashboard → **Surfaces → Add Surface → MCP Surface Starter** →
   Managed Agent → **Direct URL = this server's public URL** → save → copy the
   **Route URL** (Access Point).
3. Set `GATEWAY_URL` in `../backend/.env` to that Route URL.

> Historical note: the original `glean-mcp-surface` pointed the same chat UI at
> Glean's MCP server (Glean Assistant did the LLM/RAG). This is the neutral,
> Bedrock-optional stand-in for that upstream assistant.
