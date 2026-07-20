#!/bin/bash
# Run the chat MCP server (auth0-mcp-surface).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi
# shellcheck source=/dev/null
source venv/bin/activate

echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Load optional .env (Bedrock config)
if [ -f ".env" ]; then
  set -o allexport
  # shellcheck source=/dev/null
  source .env
  set +o allexport
fi

echo "Starting Chat MCP Server on http://localhost:${PORT:-9740} ..."
python3 mcp_server.py
