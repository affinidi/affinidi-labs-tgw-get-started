#!/usr/bin/env python3
"""
Simple A2A Agent Server

A minimal agent server that receives messages and responds with simple text.
"""

from uuid import uuid4
import uvicorn
import logging
from typing import Any, Optional

from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import AgentCard, AgentSkill, AgentCapabilities, AgentExtension, Message, TextPart, TaskStatus, TaskState, TaskStatusUpdateEvent
from a2a.utils import new_agent_text_message
from uuid import uuid4
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Extension URI for agent identity
IDENTITY_EXT_URI = "https://fabric.affinidi.io/extensions/agent-identity/v1"


class SimpleAgentExecutor(AgentExecutor):
    """Simple agent that processes messages and responds"""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute the agent logic"""
        message = context.message

        # Process response
        print("\n" + "=" * 60)
        print("MESSAGE RECEIVED:")
        print("=" * 60)
        print(message.model_dump(mode='json', exclude_none=True))
        print("=" * 60 + "\n")

        # Extract text from message parts
        text_content = []
        if message.parts:
            for part in message.parts:
                # Handle both wrapped and unwrapped parts
                part_obj = part.root if hasattr(part, 'root') else part
                if hasattr(part_obj, 'kind') and part_obj.kind == "text":
                    text_content.append(part_obj.text)

        if message.metadata:
            logger.info(
                f"[{self.agent_name}] Message metadata: {message.metadata}")
        else:
            logger.info(f"[{self.agent_name}] No message metadata")

        user_message = " ".join(
            text_content) if text_content else "No text content"
        logger.info(f"[{self.agent_name}] User message: {user_message}")

        # Generate response
        response_text = (
            f"Echo from {self.agent_name}!\n\n"
            f"You said: {user_message}\n\n"
        )

        # Create response message with extensions and metadata
        final_message = new_agent_text_message(response_text)
        final_message.task_id = message.task_id
        final_message.context_id = message.context_id
        # final_message.extensions = [IDENTITY_EXT_URI]
        # final_message.metadata = {
        #     IDENTITY_EXT_URI: {
        #         "agentIdentity": {
        #             "name": self.agent_name,
        #             "version": "1.0.0"
        #         }
        #     }
        # }

        # Create task status with the message
        final_status = TaskStatus(
            state=TaskState.completed,
            message=final_message,
            timestamp=datetime.now().isoformat()
        )

        # Create task status update event
        final_update = TaskStatusUpdateEvent(
            task_id=message.task_id,
            context_id=message.context_id,
            status=final_status,
            final=True
        )

        # Send response back
        await event_queue.enqueue_event(final_update)
        logger.info(f"[{self.agent_name}] Response sent with agent identity")

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> None:
        """Cancel execution (not supported)"""
        logger.info(f"[{self.agent_name}] Cancel requested")
        raise Exception("cancel not supported")


def create_agent_card(port: int, agent_name: str) -> AgentCard:
    """Create agent card describing the agent's capabilities"""
    skill = AgentSkill(
        id='simple-chat',
        name='Simple Chat',
        description='Responds to messages with simple text responses',
        tags=['chat', 'simple'],
        examples=['hello', 'how are you', 'tell me a joke'],
    )

    return AgentCard(
        name=agent_name,
        description='A simple A2A agent server for testing',
        url=f'http://localhost:{port}/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(
            streaming=False,
            extensions=[
                AgentExtension(
                    uri="https://fabric.affinidi.io/extensions/agent-identity/v1",
                    description='Supports agent identity exchange',
                    required=False
                ),
                # AgentExtension(
                #     uri="https://fabric.affinidi.io/extensions/custom-metadata/v1",
                #     description='Custom metadata validation',
                #     required=True
                # ),
            ]
        ),
        skills=[skill],
    )


def main(port: int = 10000, agent_name: str = "Simple A2A Agent"):
    """Run the A2A agent server"""

    logger.info("=" * 60)
    logger.info(f"{agent_name}")
    logger.info(f"Port: {port}")
    logger.info("=" * 60)

    # Create agent card
    agent_card = create_agent_card(port, agent_name)

    # Create executor
    executor = SimpleAgentExecutor(agent_name)

    # Create request handler
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    # Create A2A application
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    # Build the Starlette app
    app = server.build()

    # Add health endpoint
    async def health_check(request):
        return JSONResponse({
            "status": "healthy",
            "agent": agent_name,
            "port": port,
            "agent_card_url": f"http://localhost:{port}/.well-known/agent-card.json"
        })

    # Add HEAD support for root
    async def head_root(request):
        return Response(status_code=200)

    # Add custom routes
    app.routes.extend([
        Route("/", health_check, methods=["GET"]),
        Route("/health", health_check, methods=["GET"]),
        Route("/", head_root, methods=["HEAD"]),
    ])

    logger.info(f"Starting {agent_name} on http://localhost:{port}")
    logger.info(
        f"Agent Card: http://localhost:{port}/.well-known/agent-card.json")
    logger.info(f"Health Check: http://localhost:{port}/health")
    logger.info("")
    logger.info("Press Ctrl+C to stop the server")
    logger.info("=" * 60)

    # Run the server
    uvicorn.run(app, host='0.0.0.0', port=port)


if __name__ == "__main__":
    import sys

    # Allow port to be specified as command line argument
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 10000

    main(port=port)
