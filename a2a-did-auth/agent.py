#!/usr/bin/env python3
"""
Minimal A2A Echo Agent

just receives a text message and echoes it
back. Used to demonstrate that Agent Gateway DID Auth can protect an agent
without requiring any changes to the agent itself.
"""

from uuid import uuid4
import os
import sys
import logging
from datetime import datetime

import uvicorn
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    AgentCard,
    AgentSkill,
    AgentCapabilities,
    TaskStatus,
    TaskState,
    TaskStatusUpdateEvent,
)
from a2a.utils import new_agent_text_message

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EchoAgentExecutor(AgentExecutor):
    """Echoes back whatever text it receives."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message = context.message

        text_content = []
        if message.parts:
            for part in message.parts:
                part_obj = part.root if hasattr(part, 'root') else part
                if hasattr(part_obj, 'kind') and part_obj.kind == "text":
                    text_content.append(part_obj.text)

        user_message = " ".join(
            text_content) if text_content else "No text content"
        logger.info(f"Received: {user_message}")

        response_text = f"Echo: {user_message}"

        final_message = new_agent_text_message(response_text)
        final_message.task_id = message.task_id
        final_message.context_id = message.context_id

        final_status = TaskStatus(
            state=TaskState.completed,
            message=final_message,
            timestamp=datetime.now().isoformat()
        )

        final_update = TaskStatusUpdateEvent(
            task_id=message.task_id,
            context_id=message.context_id,
            status=final_status,
            final=True
        )

        await event_queue.enqueue_event(final_update)
        logger.info("Response sent")

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("cancel not supported")


def create_agent_card(port: int) -> AgentCard:
    skill = AgentSkill(
        id='echo',
        name='Echo',
        description='Echoes back the text it receives',
        tags=['echo', 'simple'],
        examples=['hello'],
    )

    return AgentCard(
        name="Echo Agent",
        description='A minimal A2A echo agent',
        url=os.environ.get("PUBLIC_BASE_URL",
                           f"http://localhost:{port}").rstrip("/") + "/",
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )


def main(port: int = 8001):
    logger.info("=" * 60)
    logger.info("Echo Agent")
    logger.info(f"Port: {port}")
    logger.info("=" * 60)

    agent_card = create_agent_card(port)
    executor = EchoAgentExecutor()

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    app = server.build()

    async def health_check(request):
        return JSONResponse({"status": "healthy", "agent": "Echo Agent", "port": port})

    async def head_root(request):
        return Response(status_code=200)

    app.routes.extend([
        Route("/", health_check, methods=["GET"]),
        Route("/health", health_check, methods=["GET"]),
        Route("/", head_root, methods=["HEAD"]),
    ])

    logger.info(f"Starting Echo Agent on http://localhost:{port}")
    logger.info(
        f"Agent Card: http://localhost:{port}/.well-known/agent-card.json")
    logger.info("Press Ctrl+C to stop the server")
    logger.info("=" * 60)

    uvicorn.run(app, host='0.0.0.0', port=port)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    main(port=port)
