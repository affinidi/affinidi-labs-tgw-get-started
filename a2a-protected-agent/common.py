"""Shared helpers, mock data, and responses used by all agents."""

import logging
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

IDENTITY_EXT_URI = "https://fabric.affinidi.io/extensions/agent-identity/v1"
METADATA_EXT_URI = "https://fabric.affinidi.io/extensions/agent-metadata/v1"


def get_agent_identity(
    agent_name: str,
    role: str | None = None,
    model: str | None = None,
    version: str = "1.0.0",
) -> dict:
    return {
        "name": agent_name,
        "model": model if model is not None else "bedrock/claude-3.5-sonnet",
        "role": role if role is not None else f"{agent_name} Server",
        "version": version,
    }


# ─── Generic A2A client helper ───────────────────────────────────────────────

async def call_agent(
    agent_url: str,
    user_text: str,
    caller_name: str,
    caller_role: str | None = None,
    timeout: float = 10.0,
) -> str:
    """
    Send a message to any A2A agent and return its text response.

    Args:
        agent_url:   Full URL of the target agent's JSON-RPC endpoint.
        user_text:   The message text to send.
        caller_name: Name of the calling agent (used in identity metadata).
        caller_role: Optional role override; defaults to "<caller_name> Client".
        timeout:     HTTP timeout in seconds.

    Returns:
        The agent's text reply, or an error message on failure.
    """
    # Import here to avoid a circular dependency at module level
    from a2a.client import A2AClient
    from a2a.types import Message, MessageSendParams, Part, Role, SendMessageRequest, TextPart

    try:
        async with httpx.AsyncClient(timeout=timeout) as http:
            client = A2AClient(httpx_client=http, url=agent_url)

            request = SendMessageRequest(
                id=uuid4().hex,
                params=MessageSendParams(
                    message=Message(
                        role=Role.user,
                        parts=[
                            Part(root=TextPart(kind="text", text=user_text))],
                        message_id=uuid4().hex,
                        extensions=[IDENTITY_EXT_URI],
                        metadata={
                            IDENTITY_EXT_URI: get_agent_identity(
                                caller_name,
                                model="None",
                                role=caller_role or f"{caller_name} Client",
                            )
                        },
                    )
                ),
            )

            response = await client.send_message(request)
            text = _extract_response_text(response)
            logger.info("[%s] Agent at %s replied (%d chars)",
                        caller_name, agent_url, len(text))
            return text

    except Exception as exc:
        logger.error("[%s] call_agent(%s) failed: %s",
                     caller_name, agent_url, exc)
        return (
            f"I tried to reach the agent at {agent_url} but encountered an error. "
            "Please try again in a moment."
        )


def _extract_response_text(response) -> str:
    """Pull the text out of a SendMessageResponse."""
    try:
        result = response.root
        if hasattr(result, "status") and result.status and result.status.message:
            msg = result.status.message
        elif hasattr(result, "result") and result.result:
            inner = result.result
            if hasattr(inner, "status") and inner.status and inner.status.message:
                msg = inner.status.message
            else:
                msg = inner
        else:
            return str(response.model_dump(mode="json", exclude_none=True))

        parts = []
        for p in (msg.parts or []):
            item = p.root if hasattr(p, "root") else p
            if hasattr(item, "kind") and item.kind == "text":
                parts.append(item.text)
        return "\n".join(parts) if parts else "(no text in response)"
    except Exception as exc:
        logger.warning("Could not parse agent response: %s", exc)
        return str(response)


# ─── Personal Agent mock responses ────────────────────────────────────────────

PERSONAL_RESPONSES: dict[str, str] = {
    "hello":        "Hello! I'm your personal assistant. How can I help you today?",
    "hi":           "Hi! Great to see you. What can I do for you?",
    "how are you":  "I'm doing great, thank you for asking! How can I assist you?",
    "what can you do": (
        "I can help you with:\n"
        "• Scheduling and reminders\n"
        "• Personal tasks and to-do lists\n"
        "• General information and Q&A\n"
        "• Routing financial queries to the Finance Agent\n\n"
        "What would you like to do?"
    ),
    "schedule": (
        "Your schedule for today:\n"
        "  9:00 AM – Team standup\n"
        " 11:00 AM – Project review\n"
        "  2:00 PM – Client call\n"
        "  4:00 PM – Free slot\n\n"
        "Would you like to add or modify anything?"
    ),
    "tasks": (
        "Here are your pending tasks:\n"
        "  ✅ Review Q1 report (due today)\n"
        "  ⏳ Respond to Alice's email\n"
        "  ⏳ Book flight for conference\n\n"
        "All caught up otherwise!"
    ),
    "reminder": "Sure! What would you like to be reminded about, and when?",
    "weather":  "Today's weather: ☀️ Sunny, 24°C. A perfect day to get things done!",
    "name":     "I'm your Personal Assistant – here to make your day easier!",
}


# ─── Finance Agent mock data & responses ──────────────────────────────────────

FINANCE_MOCK_DATA: dict = {
    "user": {
        "name": "Alex Johnson",
        "account_number": "****4821",
        "account_type": "Premium Checking",
        "member_since": "2018-03-15",
    },
    "balance": {"checking": 12_480.55, "savings": 34_210.00, "investment": 98_750.30},
    "recent_transactions": [
        {"date": "2026-04-28", "description": "Netflix",
            "amount": -15.99,   "category": "Entertainment"},
        {"date": "2026-04-27", "description": "Whole Foods",
            "amount": -87.43,   "category": "Groceries"},
        {"date": "2026-04-25", "description": "Salary Deposit",
            "amount": 5_200.00, "category": "Income"},
        {"date": "2026-04-24", "description": "Electric Bill",
            "amount": -124.50,  "category": "Utilities"},
        {"date": "2026-04-22", "description": "Amazon",
            "amount": -63.20,   "category": "Shopping"},
    ],
    "budget": {
        "monthly_income": 5_200.00,
        "total_expenses": 1_840.60,
        "savings_rate": "35%",
        "categories": {
            "Housing": 1_200.00,
            "Food": 450.00,
            "Transportation": 180.00,
            "Entertainment": 95.00,
            "Utilities": 140.00,
            "Other": 175.60,
        },
    },
    "investments": {
        "portfolio_value": 98_750.30,
        "monthly_return": "+2.3%",
        "ytd_return": "+12.8%",
        "holdings": [
            {"symbol": "VTI",  "shares": 45,  "value": 45_200.00},
            {"symbol": "AAPL", "shares": 20,  "value": 18_500.00},
            {"symbol": "MSFT", "shares": 15,  "value": 16_050.30},
            {"symbol": "BND",  "shares": 100, "value": 19_000.00},
        ],
    },
    "credit_score": 782,
    "loans": [
        {"type": "Mortgage", "balance": 245_000.00,
            "monthly_payment": 1_450.00, "rate": "3.75%"},
    ],
}


def _c(val: float) -> str:
    return f"${val:,.2f}"


FINANCE_RESPONSES: dict[str, str] = {
    "balance": (
        f"💰 **Account Balances for {FINANCE_MOCK_DATA['user']['name']}**\n\n"
        f"• Checking  ({FINANCE_MOCK_DATA['user']['account_number']}): {_c(FINANCE_MOCK_DATA['balance']['checking'])}\n"
        f"• Savings:    {_c(FINANCE_MOCK_DATA['balance']['savings'])}\n"
        f"• Investments: {_c(FINANCE_MOCK_DATA['balance']['investment'])}\n\n"
        f"**Total Net Worth (approx):** {_c(sum(FINANCE_MOCK_DATA['balance'].values()))}"
    ),
    "transactions": (
        "📋 **Recent Transactions**\n\n"
        + "\n".join(
            f"• {t['date']}  {t['description']:<25} {_c(t['amount']):<12} [{t['category']}]"
            for t in FINANCE_MOCK_DATA["recent_transactions"]
        )
    ),
    "budget": (
        f"📊 **Monthly Budget Summary**\n\n"
        f"• Monthly Income:  {_c(FINANCE_MOCK_DATA['budget']['monthly_income'])}\n"
        f"• Total Expenses:  {_c(FINANCE_MOCK_DATA['budget']['total_expenses'])}\n"
        f"• Savings Rate:    {FINANCE_MOCK_DATA['budget']['savings_rate']}\n\n"
        "**Spending by Category:**\n"
        + "\n".join(
            f"  - {k}: {_c(v)}"
            for k, v in FINANCE_MOCK_DATA["budget"]["categories"].items()
        )
    ),
    "investments": (
        f"📈 **Investment Portfolio**\n\n"
        f"• Portfolio Value: {_c(FINANCE_MOCK_DATA['investments']['portfolio_value'])}\n"
        f"• Monthly Return:  {FINANCE_MOCK_DATA['investments']['monthly_return']}\n"
        f"• YTD Return:      {FINANCE_MOCK_DATA['investments']['ytd_return']}\n\n"
        "**Holdings:**\n"
        + "\n".join(
            f"  - {h['symbol']}: {h['shares']} shares @ {_c(h['value'])}"
            for h in FINANCE_MOCK_DATA["investments"]["holdings"]
        )
    ),
    "credit": (
        f"💳 **Credit Score**\n\n"
        f"Your current credit score is **{FINANCE_MOCK_DATA['credit_score']}** (Excellent).\n\n"
        "Tips to maintain it:\n"
        "• Pay bills on time\n"
        "• Keep credit utilisation below 30%\n"
        "• Avoid opening too many new accounts"
    ),
    "loan": (
        "🏦 **Loans & Liabilities**\n\n"
        + "\n".join(
            f"• {l['type']}: Balance {_c(l['balance'])}, "
            f"Monthly Payment {_c(l['monthly_payment'])}, Rate {l['rate']}"
            for l in FINANCE_MOCK_DATA["loans"]
        )
    ),
    "savings": (
        f"🏦 **Savings Account**\n\n"
        f"• Current Balance:    {_c(FINANCE_MOCK_DATA['balance']['savings'])}\n"
        f"• Monthly Savings Rate: {FINANCE_MOCK_DATA['budget']['savings_rate']}\n\n"
        "You're consistently saving – great job! 🎉"
    ),
}

# Finance keywords – used by personal_agent.py to decide when to route here
FINANCE_KEYWORDS: list[str] = [
    "balance", "account", "transaction", "budget", "invest", "portfolio",
    "stock", "credit", "loan", "mortgage", "saving", "finance", "money",
    "spending", "expense", "payment", "bank", "debt", "return",
]

# Keyword → response mapping for the finance match function
FINANCE_KEYWORD_MAP: list[tuple[list[str], str]] = [
    (["balance", "account", "how much", "money"],
     FINANCE_RESPONSES["balance"]),
    (["transaction", "spent", "purchase", "recent"],
     FINANCE_RESPONSES["transactions"]),
    (["budget", "spending", "expense", "category"],
     FINANCE_RESPONSES["budget"]),
    (["invest", "portfolio", "stock", "holding", "return"],
     FINANCE_RESPONSES["investments"]),
    (["credit", "score", "fico"],
     FINANCE_RESPONSES["credit"]),
    (["loan", "mortgage", "debt", "liabilit"],
     FINANCE_RESPONSES["loan"]),
    (["saving", "save"],
     FINANCE_RESPONSES["savings"]),
]

FINANCE_DEFAULT_RESPONSE = (
    "I'm your Finance Agent. I can help with:\n"
    "• Account balances\n"
    "• Recent transactions\n"
    "• Budget & spending breakdown\n"
    "• Investment portfolio\n"
    "• Credit score\n"
    "• Loans & liabilities\n"
    "• Savings\n\n"
    "What financial information would you like to know?"
)
