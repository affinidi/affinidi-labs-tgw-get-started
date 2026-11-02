"""Deploy, list or delete the demo agent on Vertex AI Agent Engine.

Usage:
    python deploy.py deploy
    python deploy.py update     # redeploy code and AGENT_MODE to the same engine
    python deploy.py list
    python deploy.py delete
"""

import os
import sys
from importlib.metadata import version

import vertexai
from dotenv import load_dotenv
from google.genai import types

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET")
AGENT_MODE = os.environ.get("AGENT_MODE", "rules")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
DISPLAY_NAME = "gateway-demo-agent"
RESOURCE_FILE = os.path.join(HERE, ".deployed_resource_name")
API_BASE = f"https://{LOCATION}-aiplatform.googleapis.com"


def client():
    if not PROJECT_ID or not STAGING_BUCKET:
        sys.exit("Set GOOGLE_CLOUD_PROJECT and STAGING_BUCKET in .env")
    if AGENT_MODE not in {"rules", "gemini"}:
        sys.exit("AGENT_MODE must be 'rules' or 'gemini'")
    vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)
    return vertexai.Client(
        project=PROJECT_ID,
        location=LOCATION,
        http_options=types.HttpOptions(api_version="v1beta1", base_url=f"{API_BASE}/"),
    )


def engine_config():
    return {
        "display_name": DISPLAY_NAME,
        "description": "Demo A2A agent for the Agent Gateway.",
        # Same versions as the local environment, so the pickled agent loads remotely.
        "requirements": [
            f"google-cloud-aiplatform[agent_engines]=={version('google-cloud-aiplatform')}",
            f"a2a-sdk[http-server]=={version('a2a-sdk')}",
            f"cloudpickle=={version('cloudpickle')}",
            f"pydantic=={version('pydantic')}",
            "requests",
        ],
        "extra_packages": ["agent.py"],
        "env_vars": {"AGENT_MODE": AGENT_MODE, "GEMINI_MODEL": GEMINI_MODEL},
        "staging_bucket": STAGING_BUCKET,
        "http_options": {"base_url": API_BASE, "api_version": "v1beta1"},
    }


def print_endpoints(name):
    print(f"\nResource name: {name}")
    print(f"A2A endpoint : {API_BASE}/v1beta1/{name}/a2a")
    print(f"Agent card   : {API_BASE}/v1beta1/{name}/a2a/v1/card")


def deploy():
    c = client()
    os.chdir(HERE)
    from agent import a2a_agent

    print(f"Deploying {DISPLAY_NAME} (mode={AGENT_MODE}) to {LOCATION}. This takes a few minutes.")
    remote = c.agent_engines.create(agent=a2a_agent, config=engine_config())
    name = remote.api_resource.name
    with open(RESOURCE_FILE, "w") as f:
        f.write(name)
    print_endpoints(name)


def update():
    c = client()
    if not os.path.exists(RESOURCE_FILE):
        sys.exit("No .deployed_resource_name file; run deploy first.")
    name = open(RESOURCE_FILE).read().strip()
    os.chdir(HERE)
    from agent import a2a_agent

    print(f"Updating {name} (mode={AGENT_MODE}). This takes a few minutes.")
    c.agent_engines.update(name=name, agent=a2a_agent, config=engine_config())
    print_endpoints(name)


def list_engines():
    for e in client().agent_engines.list():
        print(f"{e.api_resource.display_name}  {e.api_resource.name}")


def delete():
    c = client()
    if not os.path.exists(RESOURCE_FILE):
        sys.exit("No .deployed_resource_name file; nothing to delete.")
    name = open(RESOURCE_FILE).read().strip()
    c.agent_engines.delete(name=name, force=True)
    os.remove(RESOURCE_FILE)
    print(f"Deleted {name}")


if __name__ == "__main__":
    commands = {"deploy": deploy, "update": update, "list": list_engines, "delete": delete}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(f"Usage: python deploy.py [{' | '.join(commands)}]")
    commands[sys.argv[1]]()
