#!/bin/bash

# Simple Tools REST API Server Runner

echo "================================"
echo "Simple Tools REST API Server"
echo "================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# ── Choose how to expose this server for the Agent Gateway ────────────────────
# The Agent Gateway proxies a PUBLIC endpoint. The public URL can come from the
# company proxy client, GitHub Codespaces, any hosted URL, or an ngrok tunnel.
PORT=12000
NGROK_PID=""
cleanup() { [ -n "$NGROK_PID" ] && kill "$NGROK_PID" 2>/dev/null; }
trap cleanup EXIT

echo "How do you want to expose this server for the Agent Gateway?"
echo "  1) I already have a public URL (company proxy client / Codespaces / any tunnel) — paste it"
echo "  2) Start an ngrok tunnel for me"
echo "  3) Localhost only (no public exposure)"
read -r -p "Choose [1/2/3] (default 3): " EXPOSE_CHOICE
EXPOSE_CHOICE="${EXPOSE_CHOICE:-3}"

PUBLIC_BASE_URL="http://localhost:${PORT}"

case "$EXPOSE_CHOICE" in
    1)
        read -r -p "Enter your public base URL (e.g. https://my-proxy.example.com): " ENTERED_URL
        if [ -z "$ENTERED_URL" ]; then
            echo "Error: No URL entered."
            exit 1
        fi
        PUBLIC_BASE_URL="${ENTERED_URL%/}"
        ;;
    2)
        if ! command -v ngrok &>/dev/null; then
            echo "Error: ngrok is not installed or not in PATH. Install it from https://ngrok.com/download"
            exit 1
        fi
        echo "Starting ngrok tunnel on port ${PORT}..."
        ngrok http "${PORT}" --log=stdout > /tmp/ngrok-rest-api.log 2>&1 &
        NGROK_PID=$!
        NGROK_URL=""
        for attempt in $(seq 1 20); do
            NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null \
                | python3 -c "import sys,json; t=json.load(sys.stdin).get('tunnels',[]); print(next((x['public_url'] for x in t if x['proto']=='https'), ''))" 2>/dev/null || true)
            [ -n "$NGROK_URL" ] && break
            sleep 1
        done
        if [ -z "$NGROK_URL" ]; then
            echo "Error: Could not retrieve ngrok public URL. Check /tmp/ngrok-rest-api.log for details."
            exit 1
        fi
        echo "ngrok tunnel active: ${NGROK_URL}"
        PUBLIC_BASE_URL="${NGROK_URL%/}"
        ;;
    *)
        echo "Using localhost — no public exposure."
        ;;
esac

export PUBLIC_BASE_URL
echo ""
echo "🚀 Starting REST API server on port ${PORT}..."
echo "🌐 Public URL (use this in the Agent Gateway): ${PUBLIC_BASE_URL}"
echo "📖 API docs available at: http://localhost:${PORT}/docs"
echo "📋 OpenAPI spec at: http://localhost:${PORT}/openapi.json"
echo ""

# Run the server
python api_server.py
