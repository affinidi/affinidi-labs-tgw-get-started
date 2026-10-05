#!/bin/bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PORT="${1:-10001}"
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    echo "Usage: ./run.sh [port]"
    exit 1
fi

kill_port() {
    local port="$1"
    local pids
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
        echo "Stopping process on port $port: $pids"
        kill -9 $pids
    fi
}

kill_port "$PORT"

if [[ ! -d venv ]]; then
    python3 -m venv venv
fi
source venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

export PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://localhost:${PORT}}"
echo "A2A v1.0.1 test agent: ${PUBLIC_BASE_URL}"
echo "Agent card: ${PUBLIC_BASE_URL%/}/.well-known/agent-card.json"
python a2a_server.py "$PORT"