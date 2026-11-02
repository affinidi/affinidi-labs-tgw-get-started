"""Call the agent through the Agent Gateway with an A2A SDK client.

The client holds only the gateway caller key. It has no Google credentials.

Usage:
    GATEWAY_AGENT_URL=https://<gateway-host>/<route> GATEWAY_API_KEY=<key> python client.py "USD to EUR"
"""

import asyncio
import os
import sys

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart, TransportProtocol


async def main(text: str) -> None:
    url = os.environ["GATEWAY_AGENT_URL"].rstrip("/")
    headers = {"X-API-Key": os.environ["GATEWAY_API_KEY"], "A2A-Version": "0.3"}

    async with httpx.AsyncClient(headers=headers, timeout=60) as http:
        card = await A2ACardResolver(http, url).get_agent_card()
        print(f"Agent: {card.name}  transport: {card.preferred_transport}")
        card.url = url  # send through the gateway address we were given

        client = ClientFactory(
            ClientConfig(httpx_client=http, supported_transports=[TransportProtocol.http_json])
        ).create(card)
        message = Message(message_id=os.urandom(8).hex(), role=Role.user, parts=[Part(root=TextPart(text=text))])

        async for event in client.send_message(message):
            if isinstance(event, Message):
                for part in event.parts:
                    print(f"Agent: {part.root.text}")
            else:  # (Task, update) from agents that answer with a task
                task = event[0]
                print(f"State: {task.status.state.value}")
                for artifact in task.artifacts or []:
                    for part in artifact.parts:
                        print(f"Agent: {part.root.text}")

if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "ping"))
