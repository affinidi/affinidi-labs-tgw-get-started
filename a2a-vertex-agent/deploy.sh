#!/bin/bash

# A2A Vertex Agent - Deployment Script
# Deploys the agent to Vertex AI Agent Engine
# Usage: ./deploy.sh [action]
# Actions: deploy (default), list, delete

# Default action
ACTION=${1:-deploy}

echo "=================================================="
echo "A2A Vertex Agent - Deployment Manager"
echo "=================================================="
echo "Action: $ACTION"
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
    echo "⚠️  Error: .env file not found"
    echo ""
    echo "Create and configure .env file:"
    echo "  cp .env.example .env"
    echo "  # Edit .env with your Google Cloud Project ID and settings"
    echo ""
    exit 1
fi

# Source .env to check configuration
source .env

if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    echo "⚠️  Error: GOOGLE_CLOUD_PROJECT not set in .env"
    echo ""
    echo "Please edit .env and set your Google Cloud Project ID"
    echo ""
    exit 1
fi

# Check Google Cloud authentication
echo "Checking Google Cloud authentication..."
if ! gcloud auth application-default print-access-token &>/dev/null; then
    echo "⚠️  Not authenticated with Google Cloud"
    echo ""
    echo "Please run:"
    echo "  gcloud auth login"
    echo "  gcloud auth application-default login"
    echo "  gcloud config set project $GOOGLE_CLOUD_PROJECT"
    echo ""
    exit 1
fi
echo "✓ Authenticated"
echo ""

# Verify billing is enabled (for deploy action)
if [ "$ACTION" = "deploy" ]; then
    echo "Verifying Google Cloud configuration..."
    echo "Project ID: $GOOGLE_CLOUD_PROJECT"
    echo ""
    
    # Check if Vertex AI API is enabled
    if ! gcloud services list --enabled --project=$GOOGLE_CLOUD_PROJECT 2>/dev/null | grep -q aiplatform.googleapis.com; then
        echo "⚠️  Warning: Vertex AI API may not be enabled"
        echo ""
        echo "Enable required APIs with:"
        echo "  gcloud services enable aiplatform.googleapis.com"
        echo "  gcloud services enable storage-api.googleapis.com"
        echo "  gcloud services enable cloudbuild.googleapis.com"
        echo ""
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    echo "⚠️  IMPORTANT: Ensure billing is enabled for your project"
    echo "   Vertex AI Agent deployment requires an active billing account"
    echo ""
fi

# Run the deployment script
echo "=================================================="
echo "Running: python deploy.py $ACTION"
echo "=================================================="
echo ""

python3 deploy.py "$ACTION"

DEPLOY_EXIT_CODE=$?

echo ""
echo "=================================================="

if [ $DEPLOY_EXIT_CODE -eq 0 ]; then
    case $ACTION in
        deploy)
            echo "✓ Deployment completed successfully!"
            echo ""
            echo "Next steps:"
            echo "  1. Test the deployed agent:"
            echo "     ./test.sh"
            echo "     OR"
            echo "     python a2a_client.py"
            echo ""
            echo "  2. View deployment info:"
            echo "     cat .deployed_resource_name"
            ;;
        list)
            echo "✓ List completed"
            ;;
        delete)
            echo "✓ Deletion completed"
            ;;
    esac
else
    echo "⚠️  Operation failed with exit code: $DEPLOY_EXIT_CODE"
fi

echo "=================================================="

exit $DEPLOY_EXIT_CODE
