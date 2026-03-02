# A2A Vertex AI Agent

This project demonstrates how to build and deploy an **Agent-to-Agent (A2A)** compatible agent using **Google Cloud Vertex AI Agent Engine** and the **Agent Development Kit (ADK)**.

The example agent is a Currency Exchange Agent that can retrieve exchange rates between different currencies using the Gemini AI model.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Local Testing](#local-testing)
- [Deployment to Vertex AI](#deployment-to-vertex-ai)
- [Testing the Deployed Agent](#testing-the-deployed-agent)
- [Project Structure](#project-structure)

## Prerequisites

- Python 3.10 or higher
- Google Cloud account with billing enabled
- `gcloud` CLI installed and configured

## Installation

### 1. Create a Python Virtual Environment

```bash
# Navigate to the a2a-vertex-agent directory
cd a2a-vertex-agent

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
# venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

The `requirements.txt` includes:

- `google-adk>=1.0.0` - Agent Development Kit
- `a2a-sdk>=0.3.4` - Agent-to-Agent SDK
- `google-cloud-aiplatform[agent_engines,adk]>=1.112.0` - Vertex AI Platform
- `python-dotenv>=1.0.0` - Environment variable management
- Additional dependencies for HTTP requests and web frameworks

## Configuration

### 1. Copy the Environment File

```bash
cp .env.example .env
```

### 2. Configure Environment Variables

Edit the `.env` file and set the following values:

```dotenv
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=your-project-id          # Your Google Cloud Project ID
GOOGLE_CLOUD_LOCATION=us-central1             # Default location
STAGING_BUCKET=gs://your-project-id-staging   # GCS bucket for staging
AGENT_MODEL=gemini-2.0-flash                  # AI model to use
```

**Important Configuration Notes:**

- `GOOGLE_CLOUD_PROJECT`: Replace with your actual Google Cloud project ID
- `STAGING_BUCKET`: This bucket will be created automatically during deployment. Use the format `gs://your-project-id-staging` or any unique bucket name
- `GOOGLE_CLOUD_LOCATION`: Keep as `us-central1` unless you have specific regional requirements

### 3. Authenticate with Google Cloud

```bash
# Login to Google Cloud
gcloud auth login

# Set your default project
gcloud config set project your-project-id

# Setup application default credentials for local development
gcloud auth application-default login
```

## Local Testing

You can test the agent locally before deploying to Vertex AI.

### Run Local Tests

**Using the convenience script (recommended):**

```bash
./run.sh
```

**Or run directly:**

```bash
python local_test.py
```

The `run.sh` script automatically:

- Creates a virtual environment if needed
- Installs dependencies
- Creates `.env` from `.env.example` if it doesn't exist
- Runs the local tests

The local test script runs two types of tests:

1. **Agent Card Test**: Validates that the agent card is properly configured with skills and metadata
2. **Message Send Test**: Tests the agent's ability to process and respond to queries

**Example Output:**

```
============================================================
TEST 1: handle_authenticated_agent_card
============================================================
Agent Card:
  Name: Currency Exchange Agent
  Description: An agent that can provide currency exchange rates
  Skills: get_exchange_rate

============================================================
TEST 2: on_message_send
Query: What is the exchange rate from USD to EUR today?
============================================================
Response: The current exchange rate from USD to EUR is...
```

## Deployment to Vertex AI

### Prerequisites for Deployment

Before deploying, ensure you have completed the following Google Cloud setup:

#### 1. Create a Google Cloud Account

1. Go to [https://cloud.google.com/](https://cloud.google.com/)
2. Click "Get started for free" or "Sign in"
3. Follow the prompts to create your account
4. You'll receive free credits for new accounts (typically $300 for 90 days)

#### 2. Create a Google Cloud Project

1. Visit the [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the project dropdown at the top
3. Click "New Project"
4. Enter a project name and select organization (if applicable)
5. Click "Create"
6. Note your Project ID (you'll need this for the `.env` file)

#### 3. Enable Billing

> **⚠️ IMPORTANT**: Billing must be enabled to create and deploy Vertex AI agents.

1. Navigate to [Billing in Cloud Console](https://console.cloud.google.com/billing)
2. Select "Link a billing account" or "Create billing account"
3. Follow the prompts to add payment information
4. Link the billing account to your project

**Note**: Even with free credits, you must enable billing as Vertex AI requires an active billing account. The deployment and usage will consume from your free credits first.

#### 4. Enable Required APIs

Enable the Vertex AI API and related services:

```bash
# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com

# Enable Cloud Storage API (for staging bucket)
gcloud services enable storage-api.googleapis.com

# Enable Cloud Build API (for agent deployment)
gcloud services enable cloudbuild.googleapis.com
```

Or enable via the Cloud Console:

1. Go to [APIs & Services](https://console.cloud.google.com/apis/dashboard)
2. Click "+ ENABLE APIS AND SERVICES"
3. Search for and enable:
   - Vertex AI API
   - Cloud Storage API
   - Cloud Build API

### Deploy the Agent

Once all prerequisites are met, deploy your agent:

**Using the convenience script (recommended):**

```bash
./deploy.sh
```

**Or run directly:**

```bash
python deploy.py deploy
```

The `deploy.sh` script automatically:

- Creates and activates virtual environment if needed
- Installs dependencies
- Validates `.env` configuration
- Checks Google Cloud authentication
- Verifies API enablement
- Prompts about billing requirements
- Runs the deployment

**What happens during deployment:**

1. The script initializes Vertex AI with your project configuration
2. Packages your agent code and dependencies
3. Creates a staging bucket in Google Cloud Storage (if it doesn't exist)
4. Deploys the agent to Vertex AI Agent Engine (~5 minutes)
5. Saves the deployed resource name to `.deployed_resource_name`
6. Displays the A2A endpoints for your agent

**Expected Output:**

```
Initialized Vertex AI  project=your-project-id  location=us-central1
Staging bucket: gs://your-project-id-staging

Deploying 'a2a-currency-exchange-agent' via A2aAgent (~5 minutes)...

Deployed successfully!
Resource name: projects/123456789/locations/us-central1/reasoningEngines/1234567890
Saved to: .deployed_resource_name

A2A Endpoints:
  Agent Card URL : https://us-central1-aiplatform.googleapis.com/v1beta1/projects/.../a2a/v1/card
  Messaging URL  : https://us-central1-aiplatform.googleapis.com/v1beta1/projects/.../a2a/v1/message:send
```

### Other Deployment Commands

**Using scripts:**

```bash
# List all deployed agent engines
./deploy.sh list

# Delete the deployed agent
./deploy.sh delete
```

**Or using Python directly:**

```bash
# List all deployed agent engines
python deploy.py list

# Delete the deployed agent
python deploy.py delete
```

## Testing the Deployed Agent

After successful deployment, test your agent using the A2A client.

### Run the A2A Client

The client accepts an optional `base_url` argument. If omitted, it defaults to the Vertex AI endpoint directly. Pass a custom URL to route A2A messaging through a proxy such as the Affinidi Trust Gateway.

**Using the convenience script (recommended):**

```bash
# Direct — talks to Vertex AI
./test.sh

# Via Affinidi Trust Gateway (or any proxy)
./test.sh https://<your-trust-gateway-url>/agents/evening/linear
```

**Or run directly:**

```bash
# Direct — talks to Vertex AI
python a2a_client.py

# Via Affinidi Trust Gateway (or any proxy)
python a2a_client.py https://<your-trust-gateway-url>/agents/evening/linear
```

> **How it works:** The management API call (`agent_engines.get`) always goes to the real Vertex AI endpoint. Only the A2A messaging URL (agent card URL) is overridden when a custom `base_url` is provided.

The `test.sh` script automatically:

- Checks if the agent is deployed (validates `.deployed_resource_name` exists)
- Activates virtual environment and installs dependencies if needed
- Validates `.env` configuration
- Verifies Google Cloud authentication
- Runs the A2A client (with optional base URL passed through)

**What the client does:**

1. Loads the deployed resource name from `.deployed_resource_name`
2. Connects to Vertex AI management API to look up the deployed agent
3. Fetches the remote agent card
4. Overrides the agent card URL if a custom `base_url` was provided
5. Creates an A2A SDK client with Google Cloud Bearer Token authentication
6. Sends questions and polls for responses

**Example Interaction (direct):**

```
============================================================
  A2A SDK Client — Currency Exchange Agent
============================================================
  Base URL : https://us-central1-aiplatform.googleapis.com

[1] Fetching remote agent card...
  Name   : Currency Exchange Agent
  URL    : https://us-central1-aiplatform.googleapis.com/v1beta1/projects/.../a2a/v1

[2] Building A2A SDK client...
  A2A client ready.

[4] Sending messages via A2A SDK

  You   : What is the USD to INR exchange rate?
  Agent : The current USD to INR exchange rate is approximately 84.5.
```

**Example Interaction (via Trust Gateway):**

```
============================================================
  A2A SDK Client — Currency Exchange Agent
============================================================
  Base URL : https://<your-trust-gateway-url>/agents/evening/linear

[1] Fetching remote agent card...
  Name   : Currency Exchange Agent
  URL    : https://us-central1-aiplatform.googleapis.com/v1beta1/projects/.../a2a/v1
  URL (override) : https://<your-trust-gateway-url>/agents/evening/linear

[2] Building A2A SDK client...
  A2A client ready.
```

### Testing with Different Queries

You can modify the `questions` list in `a2a_client.py` to test different currency exchange questions:

- `"What is the exchange rate from USD to GBP?"`
- `"How many Japanese Yen is 1 US dollar worth?"`
- `"Convert 100 USD to EUR"`

### Troubleshooting

**Authentication Issues:**

```bash
# Re-authenticate if needed
gcloud auth application-default login
```

**Billing Issues:**

- Verify billing is enabled: [Cloud Console Billing](https://console.cloud.google.com/billing)
- Check quota limits in [IAM & Admin > Quotas](https://console.cloud.google.com/iam-admin/quotas)

**Deployment Failures:**

- Verify all APIs are enabled
- Check that the staging bucket name is unique and follows GCS naming rules
- Ensure your project has sufficient permissions

## Project Structure

```
a2a-vertex-agent/
├── agent.py              # Agent implementation (AgentCard, Executor, LlmAgent)
├── a2a_client.py         # A2A SDK client for testing deployed agent
├── deploy.py             # Deployment logic for Vertex AI
├── local_test.py         # Local testing without deployment
├── requirements.txt      # Python dependencies
├── run.sh                # Script to run local tests
├── test.sh               # Script to test the deployed agent
├── deploy.sh             # Script to deploy/list/delete agent on Vertex AI
├── .env.example          # Environment variable template
├── .env                  # Your environment variables (create from .env.example)
└── README.md            # This file
```

### Key Files

- **`agent.py`**: Contains the complete agent definition including:
  - `AgentCard`: Describes agent capabilities and skills
  - `CurrencyAgentExecutorWithRunner`: Bridges A2A protocol with LlmAgent
  - `my_llm_agent`: Gemini-powered agent with currency exchange tools
  - `a2a_agent`: A2A-compliant wrapper for deployment

- **`local_test.py`**: Standalone tests for agent card and message handling

- **`deploy.py`**: Production deployment to Vertex AI Agent Engine

- **`a2a_client.py`**: Client application demonstrating A2A SDK usage

## References

- [Vertex AI Agent Engine Documentation](https://cloud.google.com/agent-builder/agent-engine/docs)
- [A2A Development Guide](https://docs.cloud.google.com/agent-builder/agent-engine/develop/a2a)
- [Google ADK Documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-development-kit)
- [A2A SDK Reference](https://github.com/google/a2a-sdk)

## License

See the main project LICENSE file.
