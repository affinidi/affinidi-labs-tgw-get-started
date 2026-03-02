#!/bin/bash

# MCP Client Test Script
# Runs the test client to interact with the MCP server
# Usage: ./test-mcp-proxy.sh [server_url]
# Example: ./test-mcp-proxy.sh http://localhost:12000

# Default values
DEFAULT_SERVER_URL="https://your-trust-gateway.com/mcp/karma/correct" # Fabric Gateway URL

# Get server URL from argument or use default
SERVER_URL=${1:-$DEFAULT_SERVER_URL}

echo "=================================================="
echo "MCP Test Client"
echo "=================================================="
echo "Server URL: $SERVER_URL"
echo "=================================================="
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install requests if needed
pip install -q requests

# Run the test client
python3 mcp_client.py "$SERVER_URL"

CLIENT_EXIT_CODE=$?

echo ""
echo "=================================================="
echo "Client exited with code: $CLIENT_EXIT_CODE"
echo "=================================================="

exit $CLIENT_EXIT_CODE

