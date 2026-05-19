#!/bin/bash

# MCP Client Test Script
# Runs the test client to interact with the MCP server
# Usage: ./test.sh [server_url] [api_key]
# Example: ./test.sh http://localhost:11000 my-api-key

# Default values
DEFAULT_SERVER_URL="http://localhost:11000"
# DEFAULT_SERVER_URL="https://nonblasphemous-fermentable-olimpia.ngrok-free.dev/routes/summit/royal" # Fabric Gateway URL
# DEFAULT_SERVER_URL="http://localhost:3766/routes/convert/number" # Fabric Gateway URL


DEFAULT_API_KEY="" # Set to your API key if required

# Get server URL from argument or use default
SERVER_URL=${1:-$DEFAULT_SERVER_URL}

# Get optional API key from second argument
API_KEY=${2:-$DEFAULT_API_KEY}

echo "=================================================="
echo "MCP Test Client"
echo "=================================================="
echo "Server URL: $SERVER_URL"
if [ -n "$API_KEY" ]; then
    echo "X-API-Key: (provided)"
fi
echo "=========================================="
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install requests if needed
pip install -q requests

# Run the test client
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

