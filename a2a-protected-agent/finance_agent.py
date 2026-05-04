"""
Finance Agent  –  executor, agent card, and mock data.

Handles queries about: balances, transactions, budget, investments,
credit score, loans, and savings.
"""

import logging
from datetime import datetime

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentExtension,
    AgentSkill,
    Message,
    Part,
    Role,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)
from a2a.utils import new_agent_text_message

from common import (
    IDENTITY_EXT_URI,
    METADATA_EXT_URI,
    get_agent_identity,
    FINANCE_KEYWORDS,
    FINANCE_KEYWORD_MAP,
    FINANCE_DEFAULT_RESPONSE,
)

logger = logging.getLogger(__name__)


def match(text: str) -> str:
    """Return the appropriate mock response for a finance query."""
    t = text.lower()
    for keywords, response in FINANCE_KEYWORD_MAP:
        if any(k in t for k in keywords):
            return response
    return FINANCE_DEFAULT_RESPONSE


# ─── Agent card ────────────────────────────────────────────────────────────────

def build_card(base_url: str) -> AgentCard:
    return AgentCard(
        name="Finance Agent",
        description=(
            "A finance agent that provides information about account balances, "
            "transactions, budget, investments, credit score, and loans."
        ),
        url=f"{base_url}/a2a/finance-agent/",
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
                    params=get_agent_identity("Finance Agent"),
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
                id="finance-query",
                name="Finance Query",
                description="Handles financial queries: balances, transactions, budget, investments",
                tags=["finance", "balance", "investment", "budget", "credit"],
                examples=["What's my balance?",
                          "Show recent transactions", "How are my investments?"],
            )
        ],
    )


# ─── Executor ──────────────────────────────────────────────────────────────────

class FinanceAgentExecutor(AgentExecutor):
    """Handles incoming A2A messages for the Finance Agent."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = _extract_text(context.message)
        logger.info("[FinanceAgent] Received: %s", user_text)

        reply = match(user_text)
        await _emit_reply(context.message, event_queue, "Finance Agent", reply)

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
