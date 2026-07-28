#!/bin/bash

# Simple A2A Agent Server Runner
# Usage: ./run.sh [port]
# Example: ./run.sh 10000

# Function to kill process on a given port
kill_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo "⚠️  Port $port is already in use"
        local pid
        pid=$(lsof -Pi :$port -sTCP:LISTEN -t)
        echo "Killing process $pid..."
        kill -9 $pid 2>/dev/null
        sleep 1
        echo "✓ Process killed"
        echo ""
    fi
}

# Default port
DEFAULT_PORT=10000

# Get port from argument or use default
PORT=${1:-$DEFAULT_PORT}

# Validate port number
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    echo "Error: Port must be a number"
    echo "Usage: ./run.sh [port]"
    echo "Example: ./run.sh 10000"
    exit 1
fi

echo "=================================================="
echo "Simple A2A Agent Server"
echo "=================================================="
echo "Port: $PORT"
echo "=================================================="
echo ""

# Kill any process using the port
kill_port $PORT

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
    echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# ── Choose how to expose this server for the Agent Gateway ────────────────────
# The Agent Gateway proxies a PUBLIC endpoint. The public URL can come from the
# company proxy client, GitHub Codespaces, any hosted URL, or an ngrok tunnel.
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
        ngrok http "${PORT}" --log=stdout > /tmp/ngrok-a2a.log 2>&1 &
        NGROK_PID=$!
        NGROK_URL=""
        attempt=0
        while [ "$attempt" -lt 20 ]; do
            attempt=$((attempt + 1))
            NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null \
                | python3 -c "import sys,json; t=json.load(sys.stdin).get('tunnels',[]); print(next((x['public_url'] for x in t if x['proto']=='https'), ''))" 2>/dev/null || true)
            [ -n "$NGROK_URL" ] && break
            sleep 1
        done
        if [ -z "$NGROK_URL" ]; then
            echo "Error: Could not retrieve ngrok public URL. Check /tmp/ngrok-a2a.log for details."
            exit 1
        fi
        echo "ngrok tunnel active: ${NGROK_URL}"
        PUBLIC_BASE_URL="${NGROK_URL%/}"
        ;;
    *)
        echo "Using localhost — no public exposure."
        ;;
esac

# Consumed by a2a_server.py to set the agent card URL
export PUBLIC_BASE_URL
echo "Public URL: ${PUBLIC_BASE_URL}"
echo ""

# Run the server
echo "Starting server on port $PORT..."
echo "Press Ctrl+C to stop"
echo "=================================================="
echo ""

python a2a_server.py "$PORT"

