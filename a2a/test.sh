#!/bin/bash

# A2A Client Test Script
# Runs the interactive client to chat with the A2A server
# Usage: ./test.sh [server_url]
# Example: ./test.sh http://localhost:10000

# Default values
DEFAULT_SERVER_URL="http://localhost:10000"
# DEFAULT_SERVER_URL="https://pillar-channel.trustgateway.affinidi.io/agents/strong/paris" # Fabric Gateway URL

# Get server URL from argument or use default
SERVER_URL=${1:-$DEFAULT_SERVER_URL}

echo "=================================================="
echo "A2A Interactive Client"
echo "=================================================="
echo "Server URL: $SERVER_URL"
echo "=================================================="
echo ""

# Activate virtual environment and run client
source venv/bin/activate
python a2a_client.py "$SERVER_URL"

CLIENT_EXIT_CODE=$?

echo ""
echo "=================================================="
echo "Client exited with code: $CLIENT_EXIT_CODE"
echo "=================================================="

exit $CLIENT_EXIT_CODE
