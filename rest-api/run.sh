#!/bin/bash

# Simple Tools REST API Server Runner

echo "================================"
echo "Simple Tools REST API Server"
echo "================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

echo ""
echo "🚀 Starting REST API server on port 12000..."
echo "📖 API docs available at: http://localhost:12000/docs"
echo "📋 OpenAPI spec at: http://localhost:12000/openapi.json"
echo ""

# Run the server
python api_server.py
