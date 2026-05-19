# Trust Gateway — Load Testing

A [Locust](https://locust.io)-based load testing harness for Affinidi Trust Gateway endpoints (MCP servers and A2A agents), with a built-in web UI for running and monitoring tests.

## Project structure

```
load-testing-tg/
├── data/
│   ├── endpoints.template.json  # Template — copy this to endpoints.json
│   └── endpoints.json           # Your config (gitignored — not committed)
├── locust/
│   ├── locustfile.py            # Locust test harness
│   └── requirements.txt
├── ui/
│   ├── index.html               # Two-page web UI
│   ├── server.py                # Flask backend (SSE streaming + config API)
│   └── requirements.txt
└── run.sh                       # One-shot setup + launch script
```

## First-time setup

1. **Create your endpoints file** from the template:

   ```bash
   cp data/endpoints.template.json data/endpoints.json
   ```

2. **Edit `data/endpoints.json`** — replace the placeholder URLs and call definitions with your real endpoints. See the template for annotated MCP and A2A examples.

3. **Start the UI:**

   ```bash
   ./run.sh
   # → http://127.0.0.1:9090
   ```

`run.sh` will create a virtualenv, install all dependencies, free port 9090 if busy, and start the server. It errors early if `data/endpoints.json` is missing.

> `data/endpoints.json` is gitignored. Only `endpoints.template.json` is committed.

## Web UI

### Endpoints page

All configured endpoints in a table. Click **▶** to expand a row and inspect every call variant with its full JSON-RPC payload.

### Run Tests page

1. Check/uncheck endpoints to include
2. Choose mode:
   - **Iterations** — run exactly N requests total across all users
   - **Rate** — run at a target RPS for a fixed duration
3. Set **Users (VUs)** — parallel virtual users
4. Press **▶ Run**

Results update live per endpoint (Requests, Errors, Err %, Avg ms, p95 ms).

## CLI usage

```bash
source .venv/bin/activate

# 20 requests, 5 parallel users (iterations mode)
ITERATIONS=20 locust --headless --users 5 --spawn-rate 5 \
  --run-time 24h -f locust/locustfile.py

# ~10 req/s for 1 minute (rate mode)
TOTAL_RPS=10 locust --headless --users 10 --spawn-rate 10 \
  --run-time 1m -f locust/locustfile.py

# Single endpoint only
ITERATIONS=10 ENDPOINTS=mcp_airlines locust --headless \
  --users 2 --spawn-rate 2 --run-time 24h -f locust/locustfile.py
```

## Environment variables

| Variable     | Default               | Description                               |
| ------------ | --------------------- | ----------------------------------------- |
| `ITERATIONS` | _(unset)_             | Total requests to send, then stop         |
| `TOTAL_RPS`  | _(unset)_             | Target RPS; set `--users` to match        |
| `ENDPOINTS`  | _(all active)_        | Comma-separated endpoint names to test    |
| `CONFIG`     | `data/endpoints.json` | Path to endpoint config file              |
| `LOG_ERRORS` | `3`                   | Max error responses to print per endpoint |

## Endpoint config format

`data/endpoints.json` structure:

```json
{
  "endpoints": [
    {
      "name": "my_mcp_endpoint",
      "active": true,
      "type": "mcp",
      "url": "<Trust_Gateway_MCP_Channel_Route>",
      "calls": [
        { "method": "initialize", "params": { "protocolVersion": "2024-11-05", ... } },
        { "method": "tools/list", "params": {} },
        { "method": "tools/call", "params": { "name": "<tool>", "arguments": {} } }
      ]
    },
    {
      "name": "my_a2a_agent",
      "active": true,
      "type": "a2a",
      "url": "<Trust_Gateway_Agent_Channel_Route>",
      "messages": [
        "Hello, what can you help me with?",
        "Give me a summary of today's news."
      ]
    }
  ]
}
```

Set `"active": false` to exclude an endpoint from runs without removing it.
