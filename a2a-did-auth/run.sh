#!/bin/bash

# Runs the Echo Agent AND the DID Auth Portal together.
# Config (ports, direct agent target) is read from .env, with sane defaults.
# The agent has no auth code at all - the gateway will add DID Auth in front
# of it later without any agent changes.

cd "$(dirname "$0")"

if [ ! -f .env ] && [ -f .env.example ]; then
    echo "No .env found - creating one from .env.example"
    cp .env.example .env
fi

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

AGENT_PORT=${AGENT_PORT:-8001}
PORTAL_PORT=${PORTAL_PORT:-8090}
export AGENT_URL=${AGENT_URL:-http://localhost:$AGENT_PORT}

kill_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        local pid
        pid=$(lsof -Pi :$port -sTCP:LISTEN -t)
        echo "Killing process $pid on port $port..."
        kill -9 $pid 2>/dev/null
        sleep 1
    fi
}

kill_port "$AGENT_PORT"
kill_port "$PORTAL_PORT"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt -r portal/requirements.txt

AGENT_PID=""
PORTAL_PID=""
cleanup() {
    echo ""
    echo "Stopping agent and portal..."
    [ -n "$AGENT_PID" ] && kill "$AGENT_PID" 2>/dev/null
    [ -n "$PORTAL_PID" ] && kill "$PORTAL_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "Starting Echo Agent on http://localhost:$AGENT_PORT (log: agent.log)"
python agent.py "$AGENT_PORT" > agent.log 2>&1 &
AGENT_PID=$!

echo "Starting DID Auth Portal on http://localhost:$PORTAL_PORT (log: portal.log)"
python portal/server.py "$PORTAL_PORT" > portal.log 2>&1 &
PORTAL_PID=$!

echo ""
echo "=================================================="
echo "Echo Agent : http://localhost:$AGENT_PORT"
echo "Portal     : http://localhost:$PORTAL_PORT  (open this in your browser)"
echo "=================================================="
echo "Press Ctrl+C to stop both"

wait
