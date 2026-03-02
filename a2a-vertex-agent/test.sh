#!/bin/bash

# A2A Vertex Agent - Client Test Script
# Tests the deployed agent using A2A client
# Usage: ./test.sh [base_url]
# Example (direct Vertex AI):   ./test.sh
# Example (Trust Gateway):      ./test.sh https://your-trust-gateway.com/agents/native/bandit

# Optional base URL arg — passed through to a2a_client.py
BASE_URL=${1:-""}

echo "=================================================="
if [ -n "$BASE_URL" ]; then
    echo "A2A Vertex Agent - Client Test (via Trust Gateway)"
else
    echo "A2A Vertex Agent - Client Test (direct Vertex AI)"
fi
echo "=================================================="
echo ""

if [ -n "$BASE_URL" ]; then
    echo "Trust Gateway URL : $BASE_URL (Trust Gateway)"
else
    echo "Base URL : Vertex AI default"
fi
echo ""

# Check if .deployed_resource_name exists
if [ ! -f ".deployed_resource_name" ]; then
    echo "⚠️  Error: Agent not deployed yet"
    echo ""
    echo "Deploy the agent first using:"
    echo "  ./deploy.sh"
    echo "  OR"
    echo "  python deploy.py deploy"
    echo ""
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  Warning: Virtual environment not found"
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    echo "✓ Setup complete"
    echo ""
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Error: .env file not found"
    echo ""
    echo "Create .env file from .env.example and configure it:"
    echo "  cp .env.example .env"
    echo "  # Edit .env with your Google Cloud settings"
    echo ""
    exit 1
fi

# Check authentication
echo "Checking Google Cloud authentication..."
if ! gcloud auth application-default print-access-token &>/dev/null; then
    echo "⚠️  Not authenticated with Google Cloud"
    echo ""
    echo "Please run:"
    echo "  gcloud auth application-default login"
    echo ""
    exit 1
fi
echo "✓ Authenticated"
echo ""

# Run the A2A client
echo "Testing deployed agent..."
echo ""

python3 a2a_client.py ${BASE_URL:+"$BASE_URL"}

CLIENT_EXIT_CODE=$?

echo ""
echo "=================================================="
echo "Client test completed with exit code: $CLIENT_EXIT_CODE"
echo "=================================================="

exit $CLIENT_EXIT_CODE
