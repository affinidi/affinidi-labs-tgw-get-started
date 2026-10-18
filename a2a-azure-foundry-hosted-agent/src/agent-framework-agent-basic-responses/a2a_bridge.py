# Copyright (c) 2026 Affinidi. Licensed under the Apache License 2.0.
"""Self-hosted Agent2Agent (A2A) bridge for dexter.

Foundry's native hosted-agent A2A message routing currently rejects
`SendMessage` with `HOSTED_AGENT_NOT_SUPPORTED` (confirmed 2026-10-16),
even though it happily publishes a spec-shaped agent card for the agent.
This module implements a minimal, self-hosted A2A v1.0 JSON-RPC
`SendMessage` handler and agent card directly as Starlette routes on the
hosted-agent container, so a caller that can reach the container (e.g. a
bridging prompt agent, or once Foundry wires up hosted-agent A2A routing)
gets a working implementation instead of a platform-level rejection.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from agent_framework import SupportsAgentRun
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

# Custom A2A extension carrying this agent's own identity metadata, always
# attached to every SendMessage response.
IDENTITY_EXTENSION_URI = "https://fabric.affinidi.io/extensions/agent-identity/v1"


AGENT_CARD: dict[str, Any] = {
    "name": "dexter",
    "description": (
        "A friendly, general-purpose assistant that answers questions concisely "
        "and helpfully across a wide range of everyday topics."
    ),
    "version": "1.0.0",
    "supportedInterfaces": [
        {
            "url": "",  # filled in per-request with this container's base URL
            "protocolBinding": "JSONRPC",
            "protocolVersion": "1.0",
        }
    ],
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
        "extensions": [
            {
                "uri": IDENTITY_EXTENSION_URI,
                "description": "Agent identity exchange.",
                "required": False,
            },
        ],
        "extendedAgentCard": False,
    },
    "skills": [
        {
            "id": "general-assistant",
            "name": "General assistant",
            "description": (
                "Answers general knowledge, factual, and conversational questions briefly "
                "and helpfully, covering topics such as geography, science, history, and "
                "everyday advice."
            ),
            "tags": ["general", "qa", "conversation", "assistant"],
            "examples": [
                "What's the capital of France?",
                "Explain photosynthesis in one sentence.",
                "What's a good substitute for buttermilk in a recipe?",
                "Summarize the plot of Romeo and Juliet in two lines.",
            ],
        }
    ],
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
}


def _extract_text(message: dict[str, Any]) -> str:
    """Pull the first text part out of an A2A message, tolerating legacy shapes."""
    for part in message.get("parts", []):
        if "text" in part:
            return part["text"]
    for item in message.get("content", []):
        if item.get("type") == "text" and "text" in item:
            return item["text"]
    return ""


def create_a2a_routes(agent: SupportsAgentRun) -> list[Route]:
    """Build the self-hosted agent-card and SendMessage routes for ``agent``."""

    async def agent_card(request: Request) -> JSONResponse:
        base_url = str(request.base_url).rstrip("/")
        card = dict(AGENT_CARD)
        card["supportedInterfaces"] = [{**iface, "url": f"{base_url}/a2a"} for iface in AGENT_CARD["supportedInterfaces"]]
        return JSONResponse(card)

    async def send_message(request: Request) -> JSONResponse:
        body = await request.json()
        rpc_id = body.get("id")
        method = body.get("method")
        if method != "SendMessage":
            return JSONResponse(
                {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": f"Method not found: {method}"}},
                status_code=400,
            )

        message = body.get("params", {}).get("message", {})
        text = _extract_text(message)
        if not text:
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32602, "message": "Message must contain a text part"},
                },
                status_code=400,
            )

        response = await agent.run(text)

        task_id = str(uuid.uuid4())
        context_id = message.get("contextId") or str(uuid.uuid4())

        reply: dict[str, Any] = {
            "messageId": str(uuid.uuid4()),
            "contextId": context_id,
            "taskId": task_id,
            "role": "ROLE_AGENT",
            "parts": [{"text": response.text}],
            "extensions": [IDENTITY_EXTENSION_URI],
            "metadata": {
                IDENTITY_EXTENSION_URI: {
                    "name": "Dexter Foundry Agent",
                    "model": "GPT5-mini",
                    "role": "worker",
                    "version": "4.0.0",
                }
            },
        }

        task: dict[str, Any] = {
            "id": task_id,
            "contextId": context_id,
            "status": {
                "state": "TASK_STATE_COMPLETED",
                "message": reply,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            },
            "history": [],
        }

        return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": {"task": task}})

    return [
        Route("/.well-known/agent-card.json", agent_card, methods=["GET"], name="a2a_agent_card_well_known"),
        Route("/a2a/agentCard/v1.0", agent_card, methods=["GET"], name="a2a_agent_card"),
        Route("/a2a", send_message, methods=["POST"], name="a2a_send_message"),
        # Foundry's edge does not forward arbitrary custom routes to hosted-agent
        # containers; /invocations is the one generic, externally-reachable
        # "bring your own payload" path it does forward, so it doubles as the A2A
        # SendMessage bridge for external callers until native hosted-agent A2A
        # routing is fixed.
        Route("/invocations", send_message, methods=["POST"], name="a2a_send_message_via_invocations"),
    ]