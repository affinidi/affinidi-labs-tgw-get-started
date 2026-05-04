"""
Personal Agent  –  executor, agent card, and mock responses.

Handles general personal queries (schedule, tasks, reminders, etc.).
When a finance-related keyword is detected, it uses the A2A client to
forward the message to the Finance Agent and relays the response back.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentExtension,
    AgentSkill,
    Message,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from a2a.utils import new_agent_text_message

from common import (
    IDENTITY_EXT_URI,
    METADATA_EXT_URI,
    get_agent_identity,
    FINANCE_KEYWORDS,
    PERSONAL_RESPONSES,
    call_agent,
)

load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger(__name__)

# URL of the Finance Agent – read from .env / env var; overridable at runtime by agents.py
_FINANCE_AGENT_URL: str = os.environ.get(
    "FINANCE_AGENT_URL", "http://localhost:10000/a2a/finance-agent/"
)


def _is_finance_query(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in FINANCE_KEYWORDS)


def _match_local(text: str) -> str:
    t = text.lower()
    for kw, response in PERSONAL_RESPONSES.items():
        if kw in t:
            return response
    return (
        f"I received your message: \"{text}\"\n\n"
        "I'm your personal assistant. I can help with scheduling, reminders, tasks, and more. "
        "Type 'what can you do' to see all my capabilities!"
    )


# ─── Agent card ────────────────────────────────────────────────────────────────

def build_card(base_url: str) -> AgentCard:
    return AgentCard(
        name="Personal Assistant",
        description=(
            "A personal assistant that helps you with scheduling, reminders, "
            "tasks, and general information. Automatically routes financial "
            "queries to the Finance Agent via A2A."
        ),
        url=f"{base_url}/a2a/personal-agent/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(
            streaming=False,
            extensions=[
                AgentExtension(
                    uri=IDENTITY_EXT_URI,
                    description="Supports agent identity exchange via Affinidi Trust Gateway",
                    required=False,
                    params=get_agent_identity("Personal Assistant"),
                ),
                AgentExtension(
                    uri=METADATA_EXT_URI,
                    description="Exposes agent model and runtime metadata",
                    required=False,
                ),
            ],
        ),
        skills=[
            AgentSkill(
                id="personal-chat",
                name="Personal Chat",
                description="Handles personal queries: scheduling, tasks, reminders, general Q&A",
                tags=["personal", "schedule", "tasks", "reminder"],
                examples=["What's on my schedule?",
                          "Add a reminder", "What can you do?"],
            )
        ],
    )


# ─── Executor ──────────────────────────────────────────────────────────────────

class PersonalAgentExecutor(AgentExecutor):
    """
    Handles incoming A2A messages for the Personal Agent.

    Finance-related queries are forwarded to the Finance Agent via the
    A2A client.  All other queries are answered locally.
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = _extract_text(context.message)
        logger.info("[PersonalAgent] Received: %s", user_text)

        if _is_finance_query(user_text):
            logger.info(
                "[PersonalAgent] Finance keyword detected – routing to Finance Agent")
            raw = await call_agent(
                _FINANCE_AGENT_URL,
                user_text,
                caller_name="Personal Assistant",
            )
            reply = f"🔀 *Routed to Finance Agent*\n\n{raw}"
        else:
            reply = _match_local(user_text)

        await _emit_reply(context.message, event_queue, "Personal Assistant", reply)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _extract_text(message: Message) -> str:
    parts = []
    for p in message.parts or []:
        item = p.root if hasattr(p, "root") else p
        if hasattr(item, "kind") and item.kind == "text":
            parts.append(item.text)
    return " ".join(parts)


async def _emit_reply(
    message: Message, event_queue: EventQueue, agent_name: str, text: str
) -> None:
    reply_msg = new_agent_text_message(text)
    reply_msg.task_id = message.task_id
    reply_msg.context_id = message.context_id
    reply_msg.extensions = [IDENTITY_EXT_URI]
    reply_msg.metadata = {IDENTITY_EXT_URI: get_agent_identity(agent_name)}

    await event_queue.enqueue_event(
        TaskStatusUpdateEvent(
            task_id=message.task_id,
            context_id=message.context_id,
            status=TaskStatus(
                state=TaskState.completed,
                message=reply_msg,
                timestamp=datetime.now().isoformat(),
            ),
            final=True,
        )
    )
