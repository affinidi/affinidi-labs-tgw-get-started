"""A2A agent for Vertex AI Agent Engine.

AGENT_MODE selects the reply logic at runtime:
  rules  (default) - if/else replies, no model calls, no model cost
  gemini           - one Gemini call per message through Vertex AI
"""

import logging
import os
import re

import requests
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import AgentSkill, UnsupportedOperationError
from a2a.utils import new_agent_text_message
from a2a.utils.errors import ServerError
from vertexai.preview.reasoning_engines import A2aAgent
from vertexai.preview.reasoning_engines.templates.a2a import create_agent_card

CURRENCY_PAIR = re.compile(r"\b([A-Za-z]{3})\s*(?:to|in|->|/)\s*([A-Za-z]{3})\b", re.IGNORECASE)
HELP = "Say 'ping', or ask for a rate such as 'USD to EUR'."
MAX_INPUT_CHARS = 2000
logger = logging.getLogger(__name__)


def rules_reply(text: str) -> str:
    t = text.strip()
    low = t.lower()
    if not t or low in {"help", "hi", "hello"}:
        return HELP
    if low == "ping":
        return "pong"
    m = CURRENCY_PAIR.search(t)
    if m:
        src, dst = m.group(1).upper(), m.group(2).upper()
        try:
            r = requests.get(
                "https://api.frankfurter.app/latest",
                params={"from": src, "to": dst},
                timeout=5,
            )
            r.raise_for_status()
            return f"1 {src} = {r.json()['rates'][dst]} {dst}"
        except (requests.RequestException, KeyError, ValueError):
            return f"No rate available for {src} to {dst}."
    return f"echo: {t}"


def gemini_reply(text: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(
        vertexai=True,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION"),
    )
    response = client.models.generate_content(
        model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction="You are a concise assistant. Answer in at most three sentences.",
            max_output_tokens=256,
        ),
    )
    return response.text or "No answer."


class AgentExecutorImpl(AgentExecutor):
    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        raise ServerError(error=UnsupportedOperationError())

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Reply with a single Message rather than a Task. Agent Engine runs several
        # worker processes with in-memory task stores, so a later tasks/{id} poll can
        # land on a worker that never saw the task. A Message returns the answer
        # directly in the message:send response.
        if not context.message:
            return
        text = context.get_user_input()[:MAX_INPUT_CHARS]
        try:
            if os.environ.get("AGENT_MODE", "rules") == "gemini":
                reply = gemini_reply(text)
            else:
                reply = rules_reply(text)
        except Exception:
            logger.exception("Reply generation failed")
            reply = "The agent could not process the request."
        await event_queue.enqueue_event(new_agent_text_message(reply, context_id=context.context_id))


agent_card = create_agent_card(
    agent_name="Gateway Demo Agent",
    description="Replies to ping, currency rate questions and free text.",
    skills=[
        AgentSkill(
            id="demo",
            name="Demo replies",
            description="Answers ping, looks up currency rates, otherwise echoes or answers with Gemini.",
            tags=["demo"],
            examples=["ping", "USD to EUR"],
        )
    ],
)

a2a_agent = A2aAgent(agent_card=agent_card, agent_executor_builder=AgentExecutorImpl)
