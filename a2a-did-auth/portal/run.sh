#!/bin/bash

# Runs the DID Auth Portal (backend + static frontend)
# Usage: ./run.sh [port]

DEFAULT_PORT=8090
PORT=${1:-$DEFAULT_PORT}

if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    echo "Error: Port must be a number"
    echo "Usage: ./run.sh [port]"
    exit 1
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

kill_port "$PORT"

cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "Starting DID Auth Portal on http://localhost:$PORT"
python server.py "$PORT"
