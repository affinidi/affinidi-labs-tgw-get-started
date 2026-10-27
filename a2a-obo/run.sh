#!/bin/bash
# Runs the Advisory Agent, the Orchestrator Agent and the login portal.
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

ADVISORY_PORT=${ADVISORY_PORT:-10002}
ORCH_PORT=${ORCH_PORT:-10003}
PORTAL_PORT=${PORTAL_PORT:-8095}

kill_port() {
    local pid
    pid=$(lsof -Pi :"$1" -sTCP:LISTEN -t 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "Stopping process $pid on port $1"
        kill "$pid" 2>/dev/null
        sleep 1
    fi
}
kill_port "$ADVISORY_PORT"; kill_port "$ORCH_PORT"; kill_port "$PORTAL_PORT"

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

python agents/advisory_agent.py "$ADVISORY_PORT" > logs/advisory.log 2>&1 & PIDS+=($!)
python agents/orchestrator_agent.py "$ORCH_PORT" > logs/orchestrator.log 2>&1 & PIDS+=($!)
python portal/server.py "$PORTAL_PORT" > logs/portal.log 2>&1 & PIDS+=($!)
sleep 3

for i in "${!PIDS[@]}"; do
    if ! kill -0 "${PIDS[$i]}" 2>/dev/null; then
        echo "ERROR: a service failed to start. Check logs/advisory.log, logs/orchestrator.log, logs/portal.log"
        tail -n 5 logs/advisory.log logs/orchestrator.log logs/portal.log
        exit 1
    fi
done

echo "=================================================="
echo "Advisory Agent     : http://localhost:$ADVISORY_PORT   (logs/advisory.log)"
echo "Orchestrator Agent : http://localhost:$ORCH_PORT   (logs/orchestrator.log)"
echo "Portal             : http://localhost:$PORTAL_PORT   <- open this"
echo "=================================================="
echo "Press Ctrl+C to stop all"
wait
