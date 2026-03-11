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

# Run the server
echo "Starting server on port $PORT..."
echo "Press Ctrl+C to stop"
echo "=================================================="
echo ""

python a2a_server.py "$PORT"

