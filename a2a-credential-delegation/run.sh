#!/bin/bash

# Runs the Entra-protected A2A v1.0 Echo Agent AND the login portal together.
# Config is read from .env (see .env.example for every knob).
#
# The portal reaches the agent four ways: as a guest, with a user token it
# obtains itself, and through two Agent Gateway surfaces that delegate the
# OAuth handshake. The agent validates every JWT against the tenant JWKS.

cd "$(dirname "$0")" || exit

if [ ! -f .env ] && [ -f .env.example ]; then
    echo "No .env found - creating one from .env.example"
    cp .env.example .env
fi

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

AGENT_PORT=${AGENT_PORT:-10002}
PORTAL_PORT=${PORTAL_PORT:-8095}
export AGENT_URL=${AGENT_URL:-http://localhost:$AGENT_PORT}
export PUBLIC_BASE_URL=${PUBLIC_BASE_URL:-$AGENT_URL}
export PORTAL_ORIGINS=${PORTAL_ORIGINS:-http://localhost:$PORTAL_PORT}
export PORTAL_PUBLIC_URL=${PORTAL_PUBLIC_URL:-http://localhost:$PORTAL_PORT}

AGENT_CARD_PATH="/protocols/a2a/agentCard/v1.0"

if [ -z "$ENTRA_TENANT_ID" ] || [ -z "$ENTRA_AUDIENCE" ]; then
    echo "ERROR: ENTRA_TENANT_ID and ENTRA_AUDIENCE must be set in .env"
    echo "       The agent fails closed - it will not start without them."
    exit 1
fi

if [ -z "$MICROSOFT_CLIENT_ID" ] || [ -z "$MICROSOFT_CLIENT_SECRET" ]; then
    echo "WARNING: MICROSOFT_CLIENT_ID / MICROSOFT_CLIENT_SECRET are not set."
    echo "         Entra sign-in will be disabled; only guest mode (401) works."
fi

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
pip install -q -r requirements.txt

AGENT_PID=""
PORTAL_PID=""
cleanup() {
    echo ""
    echo "Stopping agent and portal..."
    [ -n "$AGENT_PID" ] && kill "$AGENT_PID" 2>/dev/null
    [ -n "$PORTAL_PID" ] && kill "$PORTAL_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "Starting Entra-protected Echo Agent on http://localhost:$AGENT_PORT (log: agent.log)"
python agent.py "$AGENT_PORT" > agent.log 2>&1 &
AGENT_PID=$!

echo "Starting Entra Login Portal on http://localhost:$PORTAL_PORT (log: portal.log)"
python portal/server.py "$PORTAL_PORT" > portal.log 2>&1 &
PORTAL_PID=$!

sleep 3

if ! kill -0 "$AGENT_PID" 2>/dev/null; then
    echo ""
    echo "ERROR: the agent failed to start. Last lines of agent.log:"
    tail -n 20 agent.log
    exit 1
fi

echo ""
echo "=================================================="
echo "Echo Agent : $AGENT_URL"
echo "Agent Card : $AGENT_URL$AGENT_CARD_PATH"
echo "Portal     : http://localhost:$PORTAL_PORT  (open this in your browser)"
echo "=================================================="
echo "Sign in with Entra ID to chat. 'Continue as guest' is expected to fail"
echo "with HTTP 401 - the agent requires a valid Entra token."
echo ""
echo "Press Ctrl+C to stop both"

wait
