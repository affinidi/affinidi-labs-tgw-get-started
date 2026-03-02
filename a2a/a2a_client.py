#!/usr/bin/env python3
"""
Simple A2A Client for Testing

A minimal client to test the A2A agent server.
"""

import asyncio
from importlib import metadata
import httpx
import logging
import warnings
from uuid import uuid4
from typing import Any

from a2a.client import A2ACardResolver, A2AClient
from a2a.types import MessageSendParams, SendMessageRequest, TextPart

# Suppress SSL warnings
warnings.filterwarnings('ignore', category=Warning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Extension URI for agent identity
IDENTITY_EXT_URI = "https://fabric.affinidi.io/extensions/agent-identity/v1"


async def send_message(client: A2AClient, message_text: str):
    """Send a message to the A2A server and get response"""

    # Create message payload
    logger.info(f"\nSending Message...")
    message_payload: dict[str, Any] = {
        'message': {
            'role': 'user',
            'parts': [
                TextPart(kind='text', text=message_text).model_dump()
            ],
            'messageId': uuid4().hex
        }
    }

    # Add agent identity extension to response
    message_payload['message']['extensions'] = [IDENTITY_EXT_URI]
    message_payload['message']['metadata'] = {
        IDENTITY_EXT_URI: {
            "agentIdentity": {
                "name": "A2A Test Client",
                "version": "1.0.0"
            }
        }
    }

    request = SendMessageRequest(
        id=str(uuid4()),
        params=MessageSendParams(**message_payload)
    )

    # Send message and get response
    response = await client.send_message(request)

    # Process response
    print("\n" + "=" * 60)
    print("AGENT RESPONSE:")
    print("=" * 60)
    print(response.model_dump(mode='json', exclude_none=True))
    print("=" * 60 + "\n")


async def main():
    """Main function"""
    import sys

    # Default server URL
    server_url = "http://localhost:10000"

    # Parse arguments: only server URL
    if len(sys.argv) > 1:
        server_url = sys.argv[1]

    print("\n" + "=" * 60)
    print("A2A Interactive Client")
    print("=" * 60)
    print(f"Server: {server_url}")
    print("=" * 60 + "\n")

    try:
        async with httpx.AsyncClient(verify=False) as httpx_client:
            # Fetch agent card once
            logger.info("Connecting to server...")
            resolver = A2ACardResolver(
                httpx_client=httpx_client,
                base_url=server_url,
            )
            agent_card = await resolver.get_agent_card()
            logger.info(f"  Name: {agent_card.name}")
            logger.info(f"  Description: {agent_card.description}")
            logger.info(f"  Version: {agent_card.version}")

            if agent_card.capabilities and agent_card.capabilities.extensions:
                logger.info("  Extensions:")
                for ext in agent_card.capabilities.extensions:
                    logger.info(f"    - {ext.uri} (required: {ext.required})")

            # Force agent card URL to use the same protocol as server_url
            # This prevents SSL issues when agent card has HTTPS but we're connecting via HTTP
            if agent_card.url.startswith('https://') and server_url.startswith('http://'):
                agent_card.url = agent_card.url.replace('https://', 'http://')
                logger.info(f"Modified agent card URL to: {agent_card.url}")

            print(f"✓ Connected to: {agent_card.name}")
            print("\n" + "=" * 60)
            print("Type your messages below (Ctrl+C or 'exit' to quit)")
            print("=" * 60 + "\n")

            # Initialize client
            client = A2AClient(
                httpx_client=httpx_client,
                agent_card=agent_card
            )

            # Interactive loop
            while True:
                try:
                    # Get message from user
                    message = input("You: ").strip()

                    if not message:
                        print("⚠️  Message cannot be empty\n")
                        continue

                    if message.lower() in ['exit', 'quit', 'q']:
                        print("\nGoodbye! 👋\n")
                        break

                    # Send message
                    await send_message(client, message)

                except KeyboardInterrupt:
                    print("\n\nGoodbye! 👋\n")
                    break
                except Exception as e:
                    logger.error(f"Error: {e}")
                    print(f"❌ Error: {e}\n")

    except KeyboardInterrupt:
        print("\n\nGoodbye! 👋\n")
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        print(f"❌ Failed to connect to server: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
