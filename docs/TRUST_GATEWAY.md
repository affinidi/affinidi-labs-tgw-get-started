# Affinidi Trust Gateway (part of Affinidi Trust Fabric)

The Affinidi Trust Gateway (Affinidi TGW) is an enterprise-grade gateway designed specifically for the emerging Agent-to-Agent AI ecosystem. Written in Rust for maximum performance and security, it provides comprehensive trust infrastructure, observability, and governance for AI agent communications across organizational boundaries, in ways that set it apart in the emerging AI observability space.

At its core, the Affinidi TGW is a protocol-aware intercepting proxy for the Internet of AI Agents. The Gateway provides three fundamental capabilities:

- Protocol inspection (understanding A2A, AP2, UCP, MCP, OpenAI protocols)
- Identity management (issuing and validating durable and portable decentralized identities for agents to bridge the decentralized world to AI agents), and
- Intelligent routing (directing traffic based on channels, routes, and connection points)

Built on top of these foundations are advanced features for production deployments including circuit breakers, retry logic, rate limiting, real-time metrics and logging for traffic observability and management; metadata inspection and injection for use-cases such as API key
management.

## Goal: What you will build

Establish governed MCP and A2A connections by routing clients through the Trust Gateway, which manages identity, policy enforcement, and observability before forwarding requests to your local servers or cloud-deployed agents (e.g., Vertex AI Agent Engine).

![Alt text](docs/images/before-affinidi-tgw.png)
![Alt text](docs/images/after-affinidi-tgw.png)

## Prerequisites

- Access to an Affinidi project with Trust Gateway enabled (whitelisted)
- Python 3.10+ (or whatever you require) for mcp and a2a examples
- ngrok installed (for local MCP/A2A servers — not needed for Vertex AI agent)
- Ports 11000 and 10000 available (or update configurations accordingly to align)
- Google Cloud account with billing enabled (for A2A Vertex AI Agent setup only)

## Quickstart

**Local MCP / A2A servers:**

- Create Gateway configuration in Affinidi Developer portal
- Start MCP server (`cd mcp && ./run.sh`)
- Expose with ngrok
- Create MCP/A2A channel in Gateway
- Run test script against the Gateway route
- Review the agent identity injection, metrics and logs made accessible from Affinidi TGW

**A2A Vertex AI Agent (cloud-deployed, no ngrok needed):**

- Deploy Vertex AI agent (`cd a2a-vertex-agent && ./deploy.sh`)
- Create A2A channel in Gateway pointing to the Vertex AI A2A endpoint
- Run test script with the Gateway URL (`./test.sh <gateway-url>`)
- Review identity, metrics and logs in the Gateway dashboard

See below for detailed step-by-step instructions

## About Channels in Trust Gateway

Channels are the fundamental routing unit in the Gateway. Each channel defines:

- Where to listen for incoming requests (e.g., an external URL or a load balancer)
- Where to forward requests (upstream HTTP endpoint, a local MCP Proxy, or another Gateway)
- Which protocol to use (A2A, AP2, MCP, MPX, or MCP Proxy to REST endpoint)
- How to manage identity (generate a unique decentralized identifier for the agent)
- What policies to enforce (rate limits, circuit breakers, OPA rules)
- What to inject (custom metadata, identity credentials, secrets)
- What to capture (payload logging, metrics, validation results)

The powerful feature here is zero-downtime hot reload. You can modify channel configurations (change target endpoints, update rate limits, add new channels, remove old ones) and the Gateway will update without dropping in-flight requests. Existing connections complete normally, new requests immediately use the updated configuration

## Setup Trust Gateway

### Step 1: Create Trust Gateway Configuration

1. Log in to the Affinidi Developer Portal using [https://portal.affinidi.com](https://portal.affinidi.com)
2. Select your project from the top left menu (note: only whitelisted projects can create a Trust Gateway)
3. Click on `Affinidi Trust Gateway` in the left menu
4. Click `Create Configuration` and provide a name and description

![Alt text](docs/images/create-trust-gateway.png)

5. Wait until the deployment status is Complete (this may take a few minutes)
6. Once deployment state shows `Complete`, copy the Trust Gateway dashboard URL

![Alt text](docs/images/trust-gateway-done.png)

### Step 2: Register and Login to Trust Gateway Control Plane

1. Open the Trust Gateway dashboard URL in your browser
2. For first-time users:
   - Click `Register here`
   - Enter a `username`
   - Click `Register Passkey` to complete registration (first user is considered admin)

   ![Alt text](docs/images/register-tw.png)

3. For existing users:
   - Enter your `username`
   - Click `Sign in with Passkey`

   ![Alt text](docs/images/login-tw.png)

4. After successful login, you will see the dashboard

![Alt text](docs/images/dashboard.png)

## Setup MCP & A2A Server

This guide demonstrates how to route both MCP (Model Context Protocol) and A2A (Agent-to-Agent) traffic through the Trust Gateway. You'll set up local servers for each protocol and configure channels to handle the routing, identity injection, and observability.

### Clone the Sample Repository

The example repository contains ready-to-use MCP and A2A servers with test scripts.

```bash
git clone https://github.com/kamarthiparamesh/my-agents
cd my-agents
```

**Repository Structure:**

- `mcp/` - MCP server implementation with calculator and weather tools
- `a2a/` - A2A server implementation with chat capabilities
- Each directory contains:
  - `run.sh` - Script to install the dependencies and start the server
  - `test.sh` - Script to test the server

The following sections will guide you through setting up each protocol.

### [Optional] Using Your Own Setup

If you already have an MCP or A2A server running locally or prefer writing your own you can skip cloning the sample repo.
Simply ensure that:

- Your MCP or A2A server runs on a local port (e.g., http://localhost:11000 or http://localhost:10000)
- You expose it publicly using ngrok or any tunneling tool
- You configure the Trust Gateway channel to forward requests to your public URL

The Trust Gateway will apply the same routing, authentication, identity issuance, and observability features regardless of which implementation you choose.

## MCP Server Setup

Goal: route MCP JSON-RPC via Trust Gateway with observability.
Result: A stable Gateway route URL you can call from your client.

### Run MCP Server Locally

#### Start the Server

```bash
cd mcp
./run.sh
```

The script automatically creates the virtual environment, installs dependencies, and starts the server.

Available endpoints:

- `http://localhost:11000/` - JSON-RPC endpoint
- `http://localhost:11000/health` - Health check

Available tools:

- `calculator` - Perform arithmetic operations
- `weather_forecast` - Get weather forecast (mock data)

#### Expose the server publicly with ngrok

For a simple setup, the MCP server must be accessible over the internet so that Affinidi Trust Gateway can route traffic to it

Open a new terminal and run:

```bash
ngrok http 11000
```

Example output:

```
Forwarding    https://69d4-2405-201-d008-8244-70ae-d44f-6625-8504.ngrok-free.app -> http://localhost:11000
```

Note: ngrok assigns a new URL each run unless you configure a reserved domain. For a static reserved domain, visit https://dashboard.ngrok.com/domains and use:

```bash
ngrok http --url=<YOUR_NGROK_HOST> 11000
```

#### Test the Server

```bash
cd mcp

# Test locally
./test.sh http://localhost:11000

# Test via ngrok
./test.sh https://69d4-2405-201-d008-8244-70ae-d44f-6625-8504.ngrok-free.app
```

### Configure MCP Channel in Trust Gateway

Channels route traffic through the Trust Gateway, providing observability, identity management, and policy enforcement.

#### Create a Channel

1. Open the Trust Gateway dashboard and click `Channels` in the left menu

![Alt text](docs/images/channel-create-1.png)

2. Click `Add Channel` and select `MCP` protocol

![Alt text](docs/images/channel-create-2.png)

3. Enter the following details and click `Next`:
   - Channel Name: `mcp-channel-weather`
   - Listen Address (Gateway base URL): Your public gateway URL (e.g., `https://pillar-channel.trustgateway.affinidi.io`)
   - Channel Prefix: `routes`
   - Target Endpoint Type: `Direct URL`
   - Target Endpoint URL: Your MCP server public URL from ngrok

![Alt text](docs/images/channel-create-3.png)

4. Review the details and click `Create Channel`

![Alt text](docs/images/channel-create-4.png)

5. Open the newly created channel from the MCP category

![Alt text](docs/images/channels-list.png)

6. Copy the `Channel Route` URL

![Alt text](docs/images/channel-mcp.png)

7. [Optional] Enable identity for inbound clients

#### Test via Trust Gateway

```bash
cd mcp
./test.sh https://<GATEWAY_HOST>/routes/<CUSTOM_PATH>

# Example:
./test.sh https://pillar-channel.trustgateway.affinidi.io/routes/album/legend
```

After testing, view traffic metrics and logs in the channel dashboard.

![Alt text](docs/images/channel-mcp-2.png)
![Alt text](docs/images/channel-mcp-3.png)

Where to look: channel logs/metrics in dashboard

## A2A Server Setup

Goal: route MCP JSON-RPC via Trust Gateway with observability.

Result: A stable Gateway route URL you can call from your client.

### Run A2A Server Locally

#### Start the Server

```bash
cd a2a
./run.sh
```

The script automatically creates the virtual environment, installs dependencies, and starts the server.

Available endpoints:

- `http://localhost:10000/.well-known/agent-card.json` - Agent card
- `http://localhost:10000/health` - Health check
- `http://localhost:10000/` - Root endpoint

#### Expose Server via ngrok

Open a new terminal and run:

```bash
ngrok http 10000
```

Example output:

```
Forwarding    https://69d4-2405-201-d008-8244-70ae-d44f-6625-8504.ngrok-free.app -> http://localhost:10000
```

Note: ngrok creates a new domain each time. For a static domain, visit https://dashboard.ngrok.com/domains and use:

```bash
ngrok http --url=<YOUR_NGROK_HOST> 10000
```

#### Test the Server

```bash
cd a2a

# Test locally
./test.sh http://localhost:10000

# Test via ngrok
./test.sh https://69d4-2405-201-d008-8244-70ae-d44f-6625-8504.ngrok-free.app
```

### Configure A2A Channel in Trust Gateway

Channels route traffic through the Trust Gateway, providing observability, identity management, and policy enforcement.

#### Create a Channel

1. Open the Trust Gateway dashboard and click `Channels` in the left menu

![Alt text](docs/images/channel-create-1.png)

2. Click `Add Channel` and select `A2A/UCP` protocol

![Alt text](docs/images/channel-create-2.png)

3. Enter the following details and click `Next`:
   - Channel Name: `a2a-channel-chat`
   - Listen Address: Your public gateway URL (e.g., `https://pillar-channel.trustgateway.affinidi.io`)
   - Channel Prefix: `agents`
   - Target Endpoint Type: `Direct URL`
   - Target Endpoint URL: Your A2A server public URL from ngrok

![Alt text](docs/images/channel-create-3-a2a.png)

4. Review the details and click `Create Channel`

![Alt text](docs/images/channel-create-4-a2a.png)

5. Open the newly created channel from the A2A category

![Alt text](docs/images/channels-list-2.png)

6. Copy the `Channel Route` URL

![Alt text](docs/images/channel-a2a.png)

7. [Optional] Enable identity for inbound clients

#### Test via Trust Gateway

```bash
cd a2a
./test.sh https://<GATEWAY_HOST>/agents/<CUSTOM_PATH>

# Example:
./test.sh https://pillar-channel.trustgateway.affinidi.io/agents/logic/second
```

After testing, view traffic metrics and logs in the channel dashboard.

![Alt text](docs/images/channel-a2a-2.png)
![Alt text](docs/images/channel-a2a-3.png)

## A2A Vertex AI Agent Setup

Goal: route A2A traffic from a **deployed Vertex AI Agent Engine** through the Trust Gateway with observability and identity management.

Result: A stable Gateway route URL that your A2A client uses instead of calling Vertex AI directly.

> Unlike the local A2A server, the Vertex AI agent is already deployed to the cloud — no local server or ngrok is needed. The Trust Gateway points directly to your Vertex AI A2A endpoint.

### Setup and Deploy the Vertex AI Agent

The full setup guide (install, configure, local test, deploy, test deployed agent) is in the agent folder:

👉 **[a2a-vertex-agent/README.md](a2a-vertex-agent/README.md)**

Follow the README to:

1. Install dependencies and configure `.env`
2. Test locally with `./run.sh`
3. Deploy to Vertex AI with `./deploy.sh`
4. Verify the deployment with `./test.sh` (direct Vertex AI — no gateway)

After deployment, you'll have:

- A deployed resource name saved in `.deployed_resource_name`
- A Vertex AI regional base URL based on your `GOOGLE_CLOUD_LOCATION` (this is what you'll use for the Trust Gateway channel):
  ```
  https://<LOCATION>-aiplatform.googleapis.com
  # Example: https://us-central1-aiplatform.googleapis.com
  ```

### Configure A2A Channel in Trust Gateway

Channels route traffic through the Trust Gateway, providing observability, identity management, and policy enforcement.

#### Get Your Vertex AI A2A Endpoint

For the Trust Gateway channel, you only need the **base URL** — which is the Vertex AI regional endpoint based on the `GOOGLE_CLOUD_LOCATION` set in your `.env` file:

```
https://<LOCATION>-aiplatform.googleapis.com

# Example (us-central1):
https://us-central1-aiplatform.googleapis.com
```

The Trust Gateway will forward requests to this base URL and the full resource path is handled automatically.

#### Create a Channel

1. Open the Trust Gateway dashboard and click `Channels` in the left menu

2. Click `Add Channel` and select `A2A/UCP` protocol

3. Enter the following details and click `Next`:
   - Channel Name: `a2a-vertex-agent`
   - Listen Address: Your public gateway URL
   - Channel Prefix: `agents`
   - Target Endpoint Type: `Direct URL`
   - Target Endpoint URL: The Vertex AI base URL for your location (e.g., `https://us-central1-aiplatform.googleapis.com`)

4. Review the details and click `Create Channel`

5. Open the newly created channel from the A2A category

6. Copy the `Channel Route` URL — it will look like:

   ```
   https://<GATEWAY_HOST>/agents/<CHANNEL_PATH>
   ```

### Test via Trust Gateway

Pass the Gateway channel URL to the test script:

```bash
cd a2a-vertex-agent
./test.sh https://<GATEWAY_HOST>/agents/<CHANNEL_PATH>

# Example:
./test.sh https://pillar-channel.trustgateway.affinidi.io/agents/evening/linear
```

Or run the client directly:

```bash
cd a2a-vertex-agent
python a2a_client.py https://<GATEWAY_HOST>/agents/<CHANNEL_PATH>
```

> **What happens:** The A2A client still contacts the real Vertex AI management API to look up the deployed agent, but all A2A messaging (send message, get task) is routed through the Trust Gateway channel URL instead of directly to Vertex AI.

After testing, view traffic metrics and logs in the channel dashboard.

## Create Identity for MCP/A2A Client

The Trust Gateway can create decentralized identities for your MCP/A2A clients.

### Enable identity for inbound clients

1. Edit the MCP/A2A channel you created
2. Click on the `Inbound` tab
3. Under `agentIdentity` meta field, click the `+` button
4. Enter JSON attribute name as `name`, select the `Identity` checkbox, and click save
   ![Alt text](docs/images/channel-mcp-identity.png)

5. Test your MCP/A2A client again - the Trust Gateway will now create a decentralized identity for your client
   ![Alt text](docs/images/channel-mcp-identity2.png)
   ![Alt text](docs/images/channel-mcp-identity-dashboard.png)

## Sample MCP Request & Response Messages

This section demonstrates the complete message flow through the Trust Gateway, showing how requests are transformed with identity credentials.

### 1. Client Sends MCP Request

The client initiates requests with basic identity metadata in the `_meta` field.

**List Tools Request:**

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "_meta": {
    "agentIdentity": {
      "name": "MCP Test Client",
      "version": "1.0.0"
    }
  }
}
```

**Tool Call Request:**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "_meta": {
    "agentIdentity": {
      "name": "MCP Test Client",
      "version": "1.0.0"
    }
  },
  "params": {
    "name": "calculator",
    "arguments": {
      "operation": "add",
      "a": 15,
      "b": 27
    }
  }
}
```

### 2. Server Receives Request with Verifiable Identity

The Trust Gateway intercepts the request and injects a `verifiablePresentation` - a cryptographically signed credential that proves the agent's identity. This W3C Verifiable Credential is a JWT token issued and signed by the Gateway's Channel Identity.

**Request at MCP Server (after Trust Gateway processing):**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "_meta": {
    "https://fabric.affinidi.io/extensions/agent-identity-credential/v1": {
      "verifiablePresentation": {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "id": "urn:uuid:373ad064-21ed-44cb-9c3b-6e69533c101d",
        "type": ["VerifiablePresentation"],
        "holder": "did:web:pillar-channel.trustgateway.affinidi.io:channel:c034ebb9-2f02-488c-ac77-7d59862748da",
        "verifiableCredential": {
          "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://d2oeuqaac90cm.cloudfront.net/TAgentIdentityCredentialV1R0.jsonld"
          ],
          "id": "urn:uuid:612e0ac9-f548-40ad-8808-e4744183d2e8",
          "type": ["VerifiableCredential", "AgentIdentityCredential"],
          "credentialSubject": {
            "id": "did:web:pillar-channel.trustgateway.affinidi.io:channel:c034ebb9-2f02-488c-ac77-7d59862748da",
            "identityFields": {
              "agentIdentity.name": "MCP Test Client"
            }
          },
          "issuer": "did:web:pillar-channel.trustgateway.affinidi.io",
          "validFrom": "2026-02-10T12:24:42.963506295+00:00",
          "validUntil": "2027-02-10T12:24:42.963506295+00:00",
          "proof": {
            "type": "DataIntegrityProof",
            "cryptosuite": "eddsa-rdfc-2022",
            "created": "2026-02-10T12:24:42.963Z",
            "verificationMethod": "did:web:pillar-channel.trustgateway.affinidi.io#key-2",
            "proofPurpose": "assertionMethod",
            "proofValue": "z5rVkCDWaiYbXitwkU2wVTFP1q8bStdHb2ZB2QKjRDrdKsuX5AqNNbpwhEsE1288EgtNckMMRh8z41WEVoerkEsZg"
          }
        },
        "proof": {
          "type": "DataIntegrityProof",
          "cryptosuite": "eddsa-rdfc-2022",
          "created": "2026-02-10T12:24:42.966Z",
          "verificationMethod": "did:web:pillar-channel.trustgateway.affinidi.io:channel:c034ebb9-2f02-488c-ac77-7d59862748da#key-2",
          "proofPurpose": "assertionMethod",
          "expires": "2026-11-02T12:24:42.966467913+00:00",
          "proofValue": "zsFQ8PxWECsJ6fpqmExX9R32wUXts4oUfdrJnpsQHdiRNFrmHNpNdJQvB9Lztiy3TD9pemD6vuSde8E3NXj7PQth"
        }
      },
      "did": "did:web:pillar-channel.trustgateway.affinidi.io:channel:c034ebb9-2f02-488c-ac77-7d59862748da"
    }
  },
  "params": {
    "name": "calculator",
    "arguments": {
      "operation": "add",
      "a": 15,
      "b": 27
    }
  }
}
```

**Understanding the Verifiable Credential:**

- The `verifiablePresentation` field contains a W3C Verifiable Credential JSON String
- Key fields include:
  - `holder`: The agent's DID (Decentralized Identifier)
  - `credentialSubject.identityFields`: The identity metadata from the client request
  - `issuer`: The Trust Gateway's DID
  - `proof`: Cryptographic signature ensuring authenticity and integrity

### 3. Client Receives Response from Server

The server processes the request and returns a standard MCP response with its own identity metadata.

**Response from MCP Server:**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Calculation: 15 + 27 = 42"
      }
    ]
  },
  "_meta": {
    "agentIdentity": {
      "name": "Simple MCP Server"
    }
  }
}
```
