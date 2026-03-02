"""
Deploy the Currency Exchange Agent to Vertex AI Agent Engine.

Follows the reference notebook approach:
https://github.com/GoogleCloudPlatform/generative-ai/blob/main/agents/agent_engine/tutorial_a2a_on_agent_engine.ipynb

Usage:
    python deploy.py deploy     # Deploy to Agent Engine (~5 minutes)
    python deploy.py list       # List deployed engines
    python deploy.py delete     # Delete the deployed engine
"""

import os
import sys

import vertexai
from dotenv import load_dotenv
from google.genai import types

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
BUCKET_URI = os.environ.get("STAGING_BUCKET", f"gs://{PROJECT_ID}")
AGENT_DISPLAY_NAME = "a2a-currency-exchange-agent"
RESOURCE_NAME_FILE = os.path.join(
    os.path.dirname(__file__), ".deployed_resource_name")


def get_client():
    """Initialize Vertex AI and return a vertexai.Client configured for v1beta1."""
    if not PROJECT_ID:
        print("ERROR: Set GOOGLE_CLOUD_PROJECT in your .env file.")
        sys.exit(1)
    vertexai.init(project=PROJECT_ID, location=LOCATION,
                  staging_bucket=BUCKET_URI)
    client = vertexai.Client(
        project=PROJECT_ID,
        location=LOCATION,
        http_options=types.HttpOptions(
            api_version="v1beta1",
            base_url=f"https://{LOCATION}-aiplatform.googleapis.com/",
        ),
    )
    print(f"Initialized Vertex AI  project={PROJECT_ID}  location={LOCATION}")
    print(f"Staging bucket: {BUCKET_URI}")
    return client


def build_a2a_agent():
    """Build the A2aAgent wrapping the currency exchange LlmAgent."""
    from agent import a2a_agent  # imports the ready-made instance from agent.py
    return a2a_agent


def deploy():
    """Deploy the A2aAgent to Vertex AI Agent Engine using client.agent_engines.create()."""
    client = get_client()
    app = build_a2a_agent()

    print(f"\nDeploying '{AGENT_DISPLAY_NAME}' via A2aAgent (~5 minutes)...")

    remote_agent = client.agent_engines.create(
        agent=app,
        config={
            "display_name": AGENT_DISPLAY_NAME,
            "description": app.agent_card.description,
            "requirements": [
                "google-cloud-aiplatform[agent_engines,adk]>=1.112.0",
                "a2a-sdk>=0.3.4",
                "requests>=2.31.0",
                "cloudpickle",
                "pydantic",
            ],
            "extra_packages": ["./agent.py"],
            "http_options": {
                "base_url": f"https://{LOCATION}-aiplatform.googleapis.com",
                "api_version": "v1beta1",
            },
            "staging_bucket": BUCKET_URI,
        },
    )

    resource_name = remote_agent.api_resource.name
    print(f"\nDeployed successfully!")
    print(f"Resource name: {resource_name}")

    with open(RESOURCE_NAME_FILE, "w") as f:
        f.write(resource_name)
    print(f"Saved to: {RESOURCE_NAME_FILE}")

    print(f"\nA2A Endpoints:")
    print(
        f"  Agent Card URL : https://{LOCATION}-aiplatform.googleapis.com/v1beta1/{resource_name}/a2a/v1/card")
    print(
        f"  Messaging URL  : https://{LOCATION}-aiplatform.googleapis.com/v1beta1/{resource_name}/a2a/v1/message:send")


def list_engines():
    client = get_client()
    print("\nDeployed Agent Engines:")
    engines = list(client.agent_engines.list())
    if not engines:
        print("  (none found)")
    for engine in engines:
        print(
            f"  - {engine.api_resource.display_name}  |  {engine.api_resource.name}")


def delete():
    client = get_client()
    if not os.path.exists(RESOURCE_NAME_FILE):
        print("No deployed agent found (.deployed_resource_name missing).")
        sys.exit(1)
    with open(RESOURCE_NAME_FILE) as f:
        resource_name = f.read().strip()

    confirm = input(f"Delete '{resource_name}'? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    remote_agent = client.agent_engines.get(
        name=resource_name,
        config={"http_options": {
            "base_url": f"https://{LOCATION}-aiplatform.googleapis.com"}},
    )
    remote_agent.delete(force=True)
    os.remove(RESOURCE_NAME_FILE)
    print("Deleted.")


COMMANDS = {"deploy": deploy, "list": list_engines, "delete": delete}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd not in COMMANDS:
        print(f"Usage: python deploy.py [{' | '.join(COMMANDS)}]")
        sys.exit(1)
    COMMANDS[cmd]()
