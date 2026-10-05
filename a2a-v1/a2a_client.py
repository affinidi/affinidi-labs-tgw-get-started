#!/usr/bin/env python3
"""Interactive A2A v1.0 client for an agent or Agent Gateway URL."""

import asyncio
import json
import sys
from uuid import uuid4

import httpx
from google.protobuf.json_format import MessageToDict

from a2a.client.card_resolver import A2ACardResolver
from a2a.client import ClientCallContext, ClientConfig
from a2a.client.client_factory import create_client
from a2a.types import Message, Part, Role, SendMessageRequest, TaskState
from a2a.utils.errors import A2AError


IDENTITY_EXTENSION_URI = "https://fabric.affinidi.io/extensions/agent-identity/v1"
CLIENT_IDENTITY = {
    "agentIdentity": {
        "name": "A2A v1 Test Client",
        "model": "test-client",
        "role": "A2A caller",
        "version": "1.0.0",
    }
}


def print_json(title: str, payload: dict) -> None:
    print(f"\n{title}")
    print("=" * 60)
    print(json.dumps(payload, indent=2))
    print("=" * 60)


async def log_jsonrpc_request(request: httpx.Request) -> None:
    """Print the actual JSON-RPC request serialized by the A2A SDK."""
    a2a_headers = {
        name: value
        for name, value in request.headers.items()
        if name.lower() in {"a2a-version", "a2a-extensions"}
    }
    if a2a_headers:
        print_json("A2A Request Headers", a2a_headers)
    if request.method == "POST" and request.content:
        print_json("A2A JSON-RPC Request", json.loads(request.content))


def response_title(event) -> str:
    """Describe the task payload returned by the non-streaming A2A request."""
    if event.HasField("task"):
        state = TaskState.Name(event.task.status.state).removeprefix(
            "TASK_STATE_"
        )
        if state == "COMPLETED":
            return "A2A Response: Task Completed (Agent Response)"
        return f"A2A Response: Task {state.title()}"
    if event.HasField("status_update"):
        state = TaskState.Name(
            event.status_update.status.state
        ).removeprefix("TASK_STATE_")
        if state == "COMPLETED":
            return "A2A Response: Task Completed (Agent Response)"
        return f"A2A Response: Task {state.title()}"
    if event.HasField("artifact_update"):
        return "A2A Response: Artifact Update"
    return "A2A Response"


async def send_message(client, text: str) -> None:
    request = SendMessageRequest(
        message=Message(
            role=Role.ROLE_USER,
            message_id=str(uuid4()),
            parts=[Part(text=text)],
            extensions=[IDENTITY_EXTENSION_URI],
            metadata={IDENTITY_EXTENSION_URI: CLIENT_IDENTITY},
        )
    )
    context = ClientCallContext(
        service_parameters={
            "A2A-Version": "1.0",
            "A2A-Extensions": IDENTITY_EXTENSION_URI,
        }
    )
    try:
        async for event in client.send_message(request, context=context):
            print_json(
                response_title(event),
                MessageToDict(event, preserving_proto_field_name=False),
            )
    except A2AError as error:
        print_json(
            "A2A Request Error",
            {"type": type(error).__name__, "message": str(error)},
        )


async def main() -> None:
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:10001"
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        resolver = A2ACardResolver(
            httpx_client=http_client, base_url=server_url)
        agent_card = await resolver.get_agent_card()

    print("A2A Agent Card")
    print("=" * 60)
    print(f"Name: {agent_card.name}")
    print(f"Description: {agent_card.description}")
    print(f"Version: {agent_card.version}")
    print("Supported interfaces:")
    for interface in agent_card.supported_interfaces:
        print(
            f"  - {interface.protocol_binding} {interface.protocol_version}: "
            f"{interface.url}"
        )
    if agent_card.capabilities.extensions:
        print("Extensions:")
        for extension in agent_card.capabilities.extensions:
            print(f"  - {extension.uri} (required: {extension.required})")
    print("=" * 60)
    print("Type a message, or 'exit' to quit.")

    async with httpx.AsyncClient(
        timeout=10.0,
        event_hooks={"request": [log_jsonrpc_request]},
    ) as http_client:
        client = await create_client(
            agent_card,
            client_config=ClientConfig(
                streaming=False,
                httpx_client=http_client,
            ),
        )
        try:
            while True:
                text = input("You: ").strip()
                if text.lower() in {"exit", "quit", "q"}:
                    return
                if text:
                    await send_message(client, text)
        finally:
            await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nA2A client stopped.")
