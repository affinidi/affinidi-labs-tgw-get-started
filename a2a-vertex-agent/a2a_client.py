"""
A2A SDK client for the Currency Exchange Agent deployed on Vertex AI Agent Engine.

Uses the A2A SDK ClientFactory with Google ADC authentication — matching the
reference notebook approach:
https://github.com/GoogleCloudPlatform/generative-ai/blob/main/agents/agent_engine/tutorial_a2a_on_agent_engine.ipynb

SETUP — deploy first:
    cd a2a-vertex-agent
    python deploy.py deploy

Then run this client:
    python a2a_client.py
"""

import argparse
import asyncio
import os
import sys

import httpx
import vertexai
from a2a.client import ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TaskState, TextPart, TransportProtocol
from dotenv import load_dotenv
from google.auth import default
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.genai import types

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__),  ".env"))

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
RESOURCE_NAME_FILE = os.path.join(
    os.path.dirname(__file__), ".deployed_resource_name")
MAX_RETRIES = 30

# Default Vertex AI base URL — used for both management and A2A messaging.
# Override via CLI: python a2a_client.py --base-url <url>
# Example (Affinidi Trust Gateway):
#   python a2a_client.py --base-url https://pillar-channel.trustgateway.affinidi.io/agents/evening/linear
VERTEXAI_BASE_URL = f"https://{LOCATION}-aiplatform.googleapis.com"


def get_bearer_token() -> str | None:
    """Fetch a Google Cloud bearer token using Application Default Credentials."""
    try:
        credentials, _ = default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(GoogleAuthRequest())
        return credentials.token
    except Exception as e:
        print(f"Error getting credentials: {e}")
        print("Run: gcloud auth application-default login")
        return None


def load_resource_name() -> str:
    """Read the deployed resource name from file."""
    if not os.path.exists(RESOURCE_NAME_FILE):
        raise RuntimeError(
            ".deployed_resource_name not found. Run 'python deploy.py deploy' first."
        )
    with open(RESOURCE_NAME_FILE) as f:
        return f.read().strip()


async def main(base_url: str):
    print("  A2A SDK Client — Currency Exchange Agent")
    # print(f"  Base URL : {base_url}")

    # ── Load deployed resource name ──────────────────────────────
    try:
        resource_name = load_resource_name()
    except RuntimeError as e:
        print(f"\nERROR: {e}")
        return

    FINAL_BASE_URL = base_url.rstrip("/") if base_url else VERTEXAI_BASE_URL
    print(f"\n  Base URL: {FINAL_BASE_URL}")
    # ── Reconnect to the deployed agent via vertexai.Client ──────
    # Management API always uses the real Vertex AI endpoint.
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    client = vertexai.Client(
        project=PROJECT_ID,
        location=LOCATION,
        http_options=types.HttpOptions(
            api_version="v1beta1",
            base_url=FINAL_BASE_URL,
        ),
    )
    remote_agent = client.agent_engines.get(
        name=resource_name
    )

    # ── Step 1: Get the remote agent card ────────────────────────
    # print("\n[1] Fetching remote agent card...")
    remote_agent_card = await remote_agent.handle_authenticated_agent_card()
    # print(f"  Name   : {remote_agent_card.name}")
    # print(f"  URL    : {remote_agent_card.url}")

    # ── Step 2: Build the A2A SDK client ─────────────────────────
    print("\n[2] Building A2A SDK client...")
    bearer_token = get_bearer_token()
    if not bearer_token:
        return

    is_localhost = any(h in FINAL_BASE_URL for h in (
        "localhost", "127.0.0.1", "::1"))
    ssl_verify = not is_localhost

    factory = ClientFactory(
        ClientConfig(
            supported_transports=[TransportProtocol.http_json],
            use_client_preference=True,
            httpx_client=httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {bearer_token}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(60.0, connect=10.0),
                verify=ssl_verify,
            ),
        )
    )
    a2a_client = factory.create(remote_agent_card)
    print("  A2A client ready.")

    # ── Step 3: Verify with get_card ──────────────────────────────
    print("\n[3] Verifying via a2a_client.get_card()...")
    card = await a2a_client.get_card()
    print(f"  Agent : {card.name}")
    print(f"  URL   : {card.url}")
    # import json
    # print(f"\n  Full card:\n{json.dumps(card.model_dump(), indent=2)}")

    # ── Step 4: Send messages and poll for results ────────────────
    questions = [
        # "What is the exchange rate from USD to EUR today?",
        # "How many Japanese Yen is 1 US dollar worth?",
        "What is the USD to INR exchange rate?",
    ]

    print(f"\n[4] Sending messages via A2A SDK\n")
    for question in questions:
        print(f"  You   : {question}")

        # Send message
        message = Message(
            message_id=f"msg-{os.urandom(8).hex()}",
            role=Role.user,
            parts=[Part(root=TextPart(text=question))],
        )
        response_gen = a2a_client.send_message(message)
        task_id = None
        async for chunk in response_gen:
            task_object = chunk[0]
            task_id = task_object.id
            break

        if not task_id:
            print("  ERROR: no task_id returned")
            print()
            continue

        # Poll for completion
        result = None
        retries = 0
        from a2a.types import TaskQueryParams
        while True:
            try:
                result = await a2a_client.get_task(
                    TaskQueryParams(id=task_id, history_length=1)
                )
                if result.status.state in [TaskState.completed, TaskState.failed]:
                    break
                await asyncio.sleep(1)
            except Exception as e:
                status_code = getattr(e, "status_code", None)
                if status_code == 400:
                    retries += 1
                    if retries < MAX_RETRIES:
                        await asyncio.sleep(1)
                        continue
                    else:
                        print(f"  Max retries reached for task {task_id}# ")
                        raise
                raise

        # Extract answer
        if result and result.status.state == TaskState.completed and result.artifacts:
            for artifact in result.artifacts:
                if (
                    artifact.parts
                    and hasattr(artifact.parts[0], "root")
                    and hasattr(artifact.parts[0].root, "text")
                ):
                    print(f"  Agent : {artifact.parts[0].root.text}")
                    break
        elif result and result.status.state == TaskState.failed:
            print(f"  FAILED: task {task_id}")
        else:
            print(f"  No result for task {task_id}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A2A SDK client for the Currency Exchange Agent on Vertex AI"
    )
    parser.add_argument(
        "base_url",
        nargs="?",
        default=VERTEXAI_BASE_URL,
        help=(
            "Base URL for A2A messaging. Defaults to the Vertex AI endpoint. "
            "Override to route through Affinidi Trust Gateway or any proxy."
        ),
    )
    args = parser.parse_args()
    asyncio.run(main(base_url=args.base_url))
