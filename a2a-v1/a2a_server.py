#!/usr/bin/env python3
"""A2A v1.0 echo agent for Agent Gateway compatibility testing."""

import os
import sys

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.helpers.proto_helpers import new_task_from_user_message
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentExtension,
    AgentInterface,
    AgentSkill,
    Part,
)


PROTOCOL_VERSION = "1.0"
JSONRPC_BINDING = "JSONRPC"
IDENTITY_EXTENSION_URI = "https://fabric.affinidi.io/extensions/agent-identity/v1"


def get_agent_identity() -> dict[str, str]:
    return {
        "name": "A2A v1 Echo Agent",
        "model": "echo",
        "role": "A2A v1 test agent",
        "version": "1.0.0",
    }


class EchoAgentExecutor(AgentExecutor):
    """Completes each task with an echo of its text input."""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if context.current_task is None:
            await event_queue.enqueue_event(new_task_from_user_message(context.message))
        await updater.start_work()

        response = updater.new_agent_message(
            [Part(
                text=f"Echo from A2A v1.0 agent: {context.get_user_input()}")],
            metadata={IDENTITY_EXTENSION_URI: get_agent_identity()},
        )
        response.extensions.append(IDENTITY_EXTENSION_URI)
        await updater.complete(response)

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()


def create_agent_card(public_base_url: str) -> AgentCard:
    """Create a v1 agent card with its JSON-RPC endpoint explicitly declared."""
    return AgentCard(
        name="A2A v1 Echo Agent",
        description="An A2A v1.0 echo agent for Agent Gateway testing.",
        version="1.0.0",
        supported_interfaces=[
            AgentInterface(
                url=public_base_url,
                protocol_binding=JSONRPC_BINDING,
                protocol_version=PROTOCOL_VERSION,
            )
        ],
        capabilities=AgentCapabilities(
            streaming=False,
            extensions=[
                AgentExtension(
                    uri=IDENTITY_EXTENSION_URI,
                    description="Returns identity metadata for the A2A test agent.",
                    required=False,
                    params=get_agent_identity(),
                )
            ],
        ),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id="echo",
                name="Echo",
                description="Returns the text supplied by the caller.",
                tags=["test", "echo"],
                examples=["Hello, Agent Gateway"],
            )
        ],
    )


def create_app(port: int) -> Starlette:
    public_base_url = os.environ.get(
        "PUBLIC_BASE_URL", f"http://localhost:{port}"
    ).rstrip("/")
    agent_card = create_agent_card(public_base_url)
    request_handler = DefaultRequestHandler(
        agent_executor=EchoAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    async def health_check(_request):
        return JSONResponse(
            {
                "status": "healthy",
                "protocol_version": PROTOCOL_VERSION,
                "agent_card_url": (
                    f"{public_base_url}/.well-known/agent-card.json"
                ),
            }
        )

    routes = [
        *create_agent_card_routes(agent_card),
        *create_jsonrpc_routes(request_handler, "/"),
        Route("/health", health_check, methods=["GET"]),
    ]
    return Starlette(routes=routes)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 10001
    uvicorn.run(create_app(port), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
