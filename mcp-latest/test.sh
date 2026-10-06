#!/bin/bash

# MCP Streamable HTTP Test Script
# Runs the test client against the mcp-latest server's /mcp endpoint
# Usage: ./test.sh [server_base_url] [api_key]
# Example: ./test.sh http://localhost:11100 my-api-key

DEFAULT_SERVER_URL="http://localhost:11100"
DEFAULT_API_KEY="" # Set to your API key if required

SERVER_URL=${1:-$DEFAULT_SERVER_URL}
API_KEY=${2:-$DEFAULT_API_KEY}

echo "=================================================="
echo "MCP Streamable HTTP Test Client"
echo "=================================================="
echo "Server base URL: $SERVER_URL"
echo "MCP endpoint:    $SERVER_URL/mcp"
if [ -n "$API_KEY" ]; then
    echo "X-API-Key: (provided)"
fi
echo "=========================================="
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

pip install -q requests

if [ -n "$API_KEY" ]; then
    python3 mcp_client.py "$SERVER_URL" --api-key "$API_KEY"
else
    python3 mcp_client.py "$SERVER_URL"
fi

CLIENT_EXIT_CODE=$?

echo ""
echo "=================================================="
echo "Client exited with code: $CLIENT_EXIT_CODE"
echo "=================================================="

exit $CLIENT_EXIT_CODE
