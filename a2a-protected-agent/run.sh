#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT=10000
ENV_FILE=".env"
NGROK_PID=""

# ── Create .env from example if missing ───────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
  if [ -f ".env.example" ]; then
    echo "No .env found — creating from .env.example..."
    cp .env.example "$ENV_FILE"
  else
    echo "ERROR: No .env or .env.example found. Please create a .env file."
    exit 1
  fi
fi

# ── Restore .env to localhost on exit ─────────────────────────────────────────
restore_env() {
  echo ""
  echo "Stopping server — restoring .env to localhost..."
  sed -i '' "s|^BASE_URL=.*|BASE_URL=http://localhost:${PORT}|" "$ENV_FILE"
  sed -i '' "s|^PERSONAL_AGENT_URL=.*|PERSONAL_AGENT_URL=http://localhost:${PORT}/a2a/personal-agent/|" "$ENV_FILE"
  sed -i '' "s|^FINANCE_AGENT_URL=.*|FINANCE_AGENT_URL=http://localhost:${PORT}/a2a/finance-agent/|" "$ENV_FILE"
  if [ -n "$NGROK_PID" ]; then
    kill "$NGROK_PID" 2>/dev/null || true
  fi
  echo ".env restored to localhost."
}
trap restore_env EXIT

# ── Virtual environment ────────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

# ── Dependencies ───────────────────────────────────────────────────────────────
echo "Installing dependencies..."
.venv/bin/python3 -m pip install -q -r requirements.txt

# ── Ask whether to use ngrok ──────────────────────────────────────────────────
read -r -p "Use ngrok tunnel? [Y/n]: " USE_NGROK
USE_NGROK="${USE_NGROK:-Y}"

BASE_URL="http://localhost:${PORT}"

if [[ "$USE_NGROK" =~ ^[Yy]$ ]]; then
  # ── Start ngrok ─────────────────────────────────────────────────────────────
  if ! command -v ngrok &>/dev/null; then
    echo "ERROR: ngrok is not installed or not in PATH. Please install it from https://ngrok.com/download"
    exit 1
  fi

  echo "Starting ngrok tunnel on port ${PORT}..."
  ngrok http "${PORT}" --log=stdout > /tmp/ngrok-a2a.log 2>&1 &
  NGROK_PID=$!

  # Wait for ngrok to establish the tunnel and expose the public URL
  NGROK_URL=""
  for ((attempt=1; attempt<=20; attempt++)); do
    NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null \
      | .venv/bin/python3 -c "import sys,json; tunnels=json.load(sys.stdin).get('tunnels',[]); print(next((t['public_url'] for t in tunnels if t['proto']=='https'), ''))" 2>/dev/null || true)
    if [ -n "$NGROK_URL" ]; then
      break
    fi
    sleep 1
  done

  if [ -z "$NGROK_URL" ]; then
    echo "ERROR: Could not retrieve ngrok public URL. Check /tmp/ngrok-a2a.log for details."
    exit 1
  fi

  echo "ngrok tunnel active: ${NGROK_URL}"
  BASE_URL="${NGROK_URL}"

  # ── Patch .env with ngrok URL ──────────────────────────────────────────────
  sed -i '' "s|^BASE_URL=.*|BASE_URL=${BASE_URL}|" "$ENV_FILE"
  sed -i '' "s|^PERSONAL_AGENT_URL=.*|PERSONAL_AGENT_URL=${BASE_URL}/a2a/personal-agent/|" "$ENV_FILE"
  sed -i '' "s|^FINANCE_AGENT_URL=.*|FINANCE_AGENT_URL=${BASE_URL}/a2a/finance-agent/|" "$ENV_FILE"
  echo ".env updated with ngrok URL."
else
  echo "Using localhost — skipping ngrok."
fi

# Export so agents.py inherits the correct URLs regardless of .env load order
export BASE_URL
export PERSONAL_AGENT_URL="${BASE_URL}/a2a/personal-agent/"
export FINANCE_AGENT_URL="${BASE_URL}/a2a/finance-agent/"

# ── Start server ───────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Multi-Agent Server"
echo "============================================================"
echo "  Personal Assistant → ${BASE_URL}/a2a/personal-agent"
echo "  Finance Agent      → ${BASE_URL}/a2a/finance-agent"
echo ""
echo "  Agent Cards:"
echo "    ${BASE_URL}/.well-known/personal-agent.json"
echo "    ${BASE_URL}/.well-known/finance-agent.json"
echo ""
echo "  Health: ${BASE_URL}/health"
echo ""
echo "  Open chat_app.html in your browser to start chatting."
echo "============================================================"
echo ""

.venv/bin/python3 agents.py
