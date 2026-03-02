"""
A2A Currency Exchange Agent — follows the official guide:
https://docs.cloud.google.com/agent-builder/agent-engine/develop/a2a

Components defined here:
  1. AgentCard   — describes what the agent can do
  2. AgentExecutor — handles task execution using ADK Runner
  3. LlmAgent    — the underlying Gemini-powered agent with tools
  4. A2aAgent    — wraps everything into an A2A-compliant service
"""

from vertexai.preview.reasoning_engines import A2aAgent
from google.genai import types
from google.adk.sessions import InMemorySessionService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.agents import LlmAgent
from google.adk import Runner
from a2a.utils.errors import ServerError
from a2a.utils import new_agent_text_message
from a2a.types import TaskState, TextPart, UnsupportedOperationError, Part
from a2a.server.tasks import TaskUpdater
from a2a.server.events import EventQueue
from a2a.server.agent_execution import AgentExecutor, RequestContext
import os
import requests as http_requests

# ──────────────────────────────────────────────
# 1. Define the AgentCard
# ──────────────────────────────────────────────
from a2a.types import AgentCard, AgentSkill
from vertexai.preview.reasoning_engines.templates.a2a import create_agent_card

currency_skill = AgentSkill(
    id="get_exchange_rate",
    name="Get Currency Exchange Rate",
    description="Retrieves the exchange rate between two currencies on a specified date.",
    tags=["Finance", "Currency", "Exchange Rate"],
    examples=[
        "What is the exchange rate from USD to EUR?",
        "How many Japanese Yen is 1 US dollar worth today?",
    ],
)

agent_card = create_agent_card(
    agent_name="Currency Exchange Agent",
    description="An agent that can provide currency exchange rates",
    skills=[currency_skill],
)


# ──────────────────────────────────────────────
# 2. Define the AgentExecutor
# ──────────────────────────────────────────────


class CurrencyAgentExecutorWithRunner(AgentExecutor):
    """Executor that bridges A2A protocol with the currency exchange LlmAgent."""

    def __init__(self) -> None:
        """No-arg constructor — required for pickling during deployment."""
        self.agent = None
        self.runner = None

    def _init_agent(self) -> None:
        """Lazy initialization — references the module-level LlmAgent."""
        if self.agent is None:
            self.agent = my_llm_agent
            self.runner = Runner(
                app_name=self.agent.name,
                agent=self.agent,
                artifact_service=InMemoryArtifactService(),
                session_service=InMemorySessionService(),
                memory_service=InMemoryMemoryService(),
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        raise ServerError(error=UnsupportedOperationError())

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        if self.agent is None:
            self._init_agent()  # Lazy-initialize on first call

        if not context.message:
            return

        user_id = (
            context.message.metadata.get("user_id")
            if context.message and context.message.metadata
            else "a2a_user"
        )

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            await updater.submit()
        await updater.start_work()

        query = context.get_user_input()
        content = types.Content(role="user", parts=[types.Part(text=query)])

        try:
            session = await self.runner.session_service.get_session(
                app_name=self.runner.app_name,
                user_id=user_id,
                session_id=context.context_id,
            ) or await self.runner.session_service.create_session(
                app_name=self.runner.app_name,
                user_id=user_id,
                session_id=context.context_id,
            )

            final_event = None
            async for event in self.runner.run_async(
                session_id=session.id,
                user_id=user_id,
                new_message=content,
            ):
                if event.is_final_response():
                    final_event = event

            if final_event and final_event.content and final_event.content.parts:
                response_text = "".join(
                    part.text
                    for part in final_event.content.parts
                    if hasattr(part, "text") and part.text
                )
                if response_text:
                    await updater.add_artifact(
                        [TextPart(text=response_text)],
                        name="result",
                    )
                    await updater.complete()
                    return

            await updater.update_status(
                TaskState.failed,
                message=new_agent_text_message(
                    "Failed to generate a final response with text content."
                ),
                final=True,
            )

        except Exception as e:
            await updater.update_status(
                TaskState.failed,
                message=new_agent_text_message(f"An error occurred: {str(e)}"),
                final=True,
            )
            raise


# ──────────────────────────────────────────────
# 3. Define the tool + LlmAgent
# ──────────────────────────────────────────────
def get_exchange_rate(
    currency_from: str = "USD",
    currency_to: str = "EUR",
    currency_date: str = "latest",
):
    """Retrieves the exchange rate between two currencies on a specified date.

    Uses the Frankfurter API (https://api.frankfurter.app/) to obtain
    exchange rate data.
    """
    try:
        response = http_requests.get(
            f"https://api.frankfurter.app/{currency_date}",
            params={"from": currency_from, "to": currency_to},
        )
        response.raise_for_status()
        return response.json()
    except http_requests.exceptions.RequestException as e:
        return {"error": str(e)}


my_llm_agent = LlmAgent(
    model=os.environ.get("AGENT_MODEL", "gemini-2.0-flash"),
    name="currency_exchange_agent",
    description="An agent that can provide currency exchange rates.",
    instruction="""You are a helpful currency exchange assistant.
                   Use the get_exchange_rate tool to answer user questions.
                   If the tool returns an error, inform the user about the error.""",
    tools=[get_exchange_rate],
)


# ──────────────────────────────────────────────
# 4. Create the A2aAgent (local instance)
# ──────────────────────────────────────────────

a2a_agent = A2aAgent(
    agent_card=agent_card,
    # class, not lambda — picklable for deployment
    agent_executor_builder=CurrencyAgentExecutorWithRunner,
)
a2a_agent.set_up()
