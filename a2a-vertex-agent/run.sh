#!/bin/bash

# A2A Vertex Agent - Local Test Runner
# Runs local tests without deploying to Vertex AI
# Usage: ./run.sh

echo "=================================================="
echo "A2A Vertex Agent - Local Test"
echo "=================================================="
echo ""

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

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  Please edit .env and set your configuration values"
    echo "   Then run this script again."
    echo ""
    exit 1
fi

# Run local tests
echo "=================================================="
echo "Running local tests..."
echo "=================================================="
echo ""

python3 local_test.py

TEST_EXIT_CODE=$?

echo ""
echo "=================================================="
echo "Tests completed with exit code: $TEST_EXIT_CODE"
echo "=================================================="

exit $TEST_EXIT_CODE
