"""
Local tests for the A2A Currency Exchange Agent.

Follows the official guide:
https://docs.cloud.google.com/agent-builder/agent-engine/develop/a2a

Run:
    cd vertex-agents/adk-agent
    python local_test.py
"""

import asyncio
import json

from starlette.requests import Request

# Import the ready-made a2a_agent from agent.py
from agent import a2a_agent


# ──────────────────────────────────────────────
# Test 1: handle_authenticated_agent_card
# ──────────────────────────────────────────────
async def test_agent_card():
    print("=" * 60)
    print("TEST 1: handle_authenticated_agent_card")
    print("=" * 60)
    response = await a2a_agent.handle_authenticated_agent_card(
        request=None, context=None
    )
    print(response)
    print()
    return response


# ──────────────────────────────────────────────
# Test 2: on_message_send
# ──────────────────────────────────────────────
async def test_message_send(query: str = "What is the exchange rate from USD to EUR today?"):
    print("=" * 60)
    print("TEST 2: on_message_send")
    print(f"Query: {query}")
    print("=" * 60)

    message_data = {
        "message": {
            "messageId": "local-test-message-id",
            "content": [{"text": query}],
            "role": "ROLE_USER",
        },
    }

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "headers": [(b"content-type", b"application/json")],
    }

    async def receive():
        byte_data = json.dumps(message_data).encode("utf-8")
        return {"type": "http.request", "body": byte_data, "more_body": False}

    post_request = Request(scope, receive=receive)

    send_message_response = await a2a_agent.on_message_send(
        request=post_request, context=None
    )
    print(send_message_response)
    print()
    return send_message_response


# ──────────────────────────────────────────────
# Test 3: on_get_task
# ──────────────────────────────────────────────
async def test_get_task(task_id: str):
    print("=" * 60)
    print("TEST 3: on_get_task")
    print(f"Task ID: {task_id}")
    print("=" * 60)

    task_data = {"id": task_id}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "headers": [],
        "query_string": b"",
        "path_params": task_data,
    }

    async def empty_receive():
        return {"type": "http.disconnect"}

    get_request = Request(scope, empty_receive)

    task_status_response = await a2a_agent.on_get_task(
        request=get_request, context=None
    )
    print(f"Successfully retrieved status for Task ID: {task_id}")
    print("\nFull task status response:")
    print(task_status_response)
    print()
    return task_status_response


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
async def main():
    # Test 1 — agent card
    await test_agent_card()

    # Test 2 — send a message
    send_response = await test_message_send(
        "What is the exchange rate from USD to EUR today?"
    )

    # Test 3 — retrieve task status using the task ID from Test 2
    try:
        task_id = send_response["task"]["id"]
        await test_get_task(task_id)
    except (KeyError, TypeError) as e:
        print(f"Could not extract task ID from send_response: {e}")
        print("Raw send_response:", send_response)


if __name__ == "__main__":
    asyncio.run(main())
