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

# ── Resolve a native uv ─────────────────────────────────────────────────────────
# cryptography (via a2a-sdk) only ships arm64 macOS wheels, so on Apple Silicon the
# venv MUST be arm64 — otherwise pip tries to compile it from Rust source and fails.
# Prefer the user-local uv (installed native) over any x86_64 Homebrew uv on PATH.
if [ -x "$HOME/.local/bin/uv" ]; then
  UV="$HOME/.local/bin/uv"
elif command -v uv &>/dev/null; then
  UV="$(command -v uv)"
else
  echo "ERROR: uv is not installed. Install it with:"
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

HOST_ARCH="$(uname -m)"
if [ "$HOST_ARCH" = "arm64" ] && ! file "$UV" | grep -q 'arm64'; then
  echo "ERROR: '$UV' is not an arm64 binary but this is an Apple Silicon Mac."
  echo "An x86_64 venv forces a from-source build of cryptography that will fail."
  echo "Install a native arm64 uv, then re-run:"
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

# ── Virtual environment ────────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment (Python 3.13)..."
  "$UV" venv --python 3.13 .venv
fi

# Guard against a stale x86_64 venv on an arm64 host.
if [ "$HOST_ARCH" = "arm64" ] && ! file .venv/bin/python3 | grep -q 'arm64'; then
  echo "ERROR: existing .venv is not arm64. Remove it and re-run: rm -rf .venv"
  exit 1
fi

source .venv/bin/activate

# ── Dependencies ───────────────────────────────────────────────────────────────
echo "Installing dependencies..."
"$UV" pip install -q -r requirements.txt

# ── Choose how to expose this server for the Agent Gateway ────────────────────
# The Agent Gateway proxies a PUBLIC endpoint. The public URL can come from the
# company proxy client, GitHub Codespaces, any hosted URL, or an ngrok tunnel.
echo ""
echo "How do you want to expose this server for the Agent Gateway?"
echo "  1) I already have a public URL (company proxy client / Codespaces / any tunnel) — paste it"
echo "  2) Start an ngrok tunnel for me"
echo "  3) Localhost only (no public exposure)"
read -r -p "Choose [1/2/3] (default 3): " EXPOSE_CHOICE
EXPOSE_CHOICE="${EXPOSE_CHOICE:-3}"

BASE_URL="http://localhost:${PORT}"

case "$EXPOSE_CHOICE" in
  1)
    read -r -p "Enter your public base URL (e.g. https://my-proxy.example.com): " PUBLIC_BASE_URL
    if [ -z "$PUBLIC_BASE_URL" ]; then
      echo "ERROR: No URL entered."
      exit 1
    fi
    BASE_URL="${PUBLIC_BASE_URL%/}"
    ;;
  2)
    if ! command -v ngrok &>/dev/null; then
      echo "ERROR: ngrok is not installed or not in PATH. Please install it from https://ngrok.com/download"
      exit 1
    fi
    echo "Starting ngrok tunnel on port ${PORT}..."
    ngrok http "${PORT}" --log=stdout > /tmp/ngrok-a2a-protected.log 2>&1 &
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
      echo "ERROR: Could not retrieve ngrok public URL. Check /tmp/ngrok-a2a-protected.log for details."
      exit 1
    fi

    echo "ngrok tunnel active: ${NGROK_URL}"
    BASE_URL="${NGROK_URL%/}"
    ;;
  *)
    echo "Using localhost — no public exposure."
    ;;
esac

# ── Patch .env with the chosen public URL ─────────────────────────────────────
sed -i '' "s|^BASE_URL=.*|BASE_URL=${BASE_URL}|" "$ENV_FILE"
sed -i '' "s|^PERSONAL_AGENT_URL=.*|PERSONAL_AGENT_URL=${BASE_URL}/a2a/personal-agent/|" "$ENV_FILE"
sed -i '' "s|^FINANCE_AGENT_URL=.*|FINANCE_AGENT_URL=${BASE_URL}/a2a/finance-agent/|" "$ENV_FILE"
echo "Public URL: ${BASE_URL}"

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
