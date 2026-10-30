#!/bin/bash
# Runs the Personal Agent (A2A v1.0) and the Entra login portal.
# Config is read from .env (see .env.example).

cd "$(dirname "$0")" || exit

if [ ! -f .env ] && [ -f .env.example ]; then
    echo "No .env found - creating one from .env.example. Fill it in and re-run."
    cp .env.example .env
    exit 1
fi

set -a
source .env
set +a

AGENT_PORT=${AGENT_PORT:-10004}
PORTAL_PORT=${PORTAL_PORT:-8097}

kill_port() {
    local pid
    pid=$(lsof -Pi :"$1" -sTCP:LISTEN -t 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "Stopping process $pid on port $1"
        kill "$pid" 2>/dev/null
        sleep 1
    fi
}
kill_port "$AGENT_PORT"; kill_port "$PORTAL_PORT"

if [ ! -d venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

mkdir -p logs

PIDS=()
cleanup() { echo; echo "Stopping..."; kill "${PIDS[@]}" 2>/dev/null; }
trap cleanup EXIT INT TERM

python agents/delegate_agent.py "$AGENT_PORT" > logs/agent.log 2>&1 & PIDS+=($!)
python portal/server.py "$PORTAL_PORT" > logs/portal.log 2>&1 & PIDS+=($!)
sleep 3

for pid in "${PIDS[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "ERROR: a service failed to start. Check logs/agent.log and logs/portal.log"
        tail -n 5 logs/agent.log logs/portal.log
        exit 1
    fi
done

echo "=================================================="
echo "${AGENT_NAME:-Personal Agent}: http://localhost:$AGENT_PORT   (logs/agent.log)"
echo "Agent card   : http://localhost:$AGENT_PORT/.well-known/agent-card.json"
echo "MCP          : ${MCP_GATEWAY_URL:-${MCP_URL:-<not set>}}"
[ -n "${AGENT_GATEWAY_URL:-}" ] && echo "Agent via GW : $AGENT_GATEWAY_URL"
echo "Portal       : ${PORTAL_URL:-http://localhost:$PORTAL_PORT}   <- open this"
echo "=================================================="
echo "Press Ctrl+C to stop all"
wait
