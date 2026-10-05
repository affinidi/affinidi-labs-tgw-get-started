#!/usr/bin/env python3
"""Verify A2A v1 card discovery and a JSON-RPC message round trip."""

import asyncio
import sys
from uuid import uuid4

import httpx

from a2a.client import ClientConfig
from a2a.client.client_factory import create_client
from a2a.types import Message, Part, Role, SendMessageRequest, TaskState


async def main() -> None:
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:10001"
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        response = await http_client.get(
            f"{server_url.rstrip('/')}/.well-known/agent-card.json"
        )
        response.raise_for_status()
        card = response.json()

    interfaces = card.get("supportedInterfaces", [])
    assert any(
        interface.get("protocolVersion") == "1.0"
        and interface.get("protocolBinding") == "JSONRPC"
        for interface in interfaces
    ), "agent card does not advertise A2A v1.0 JSON-RPC"
    assert any(
        extension.get("uri")
        == "https://fabric.affinidi.io/extensions/agent-identity/v1"
        for extension in card.get("capabilities", {}).get("extensions", [])
    ), "agent card does not advertise the agent identity extension"

    client = await create_client(
        server_url,
        client_config=ClientConfig(streaming=False),
    )
    try:
        request = SendMessageRequest(
            message=Message(
                role=Role.ROLE_USER,
                message_id=str(uuid4()),
                parts=[Part(text="gateway v1 smoke test")],
            )
        )
        events = [event async for event in client.send_message(request)]
    finally:
        await client.close()

    assert events, "message:send returned no events"
    completed_tasks = [
        event.task
        for event in events
        if event.HasField("task")
        and event.task.status.state == TaskState.TASK_STATE_COMPLETED
    ]
    assert completed_tasks, "message:send did not return a completed task"
    assert (
        "gateway v1 smoke test"
        in completed_tasks[-1].status.message.parts[0].text
    )
    response_message = completed_tasks[-1].status.message
    assert (
        "https://fabric.affinidi.io/extensions/agent-identity/v1"
        in response_message.extensions
    ), "response does not declare the agent identity extension"
    assert (
        response_message.metadata[
            "https://fabric.affinidi.io/extensions/agent-identity/v1"
        ]["name"]
        == "A2A v1 Echo Agent"
    ), "response does not include the expected agent identity"
    print("PASS: A2A v1.0 card discovery and message round trip succeeded")


if __name__ == "__main__":
    asyncio.run(main())
