#!/usr/bin/env python3
"""Orchestrator Agent - receives the user's token, performs the OBO exchange, and
calls the Security Advisory Agent with the resulting OBO token.

  user token  (aud = Orchestrator API, sub/oid = user, appid = Portal)
       |  grant_type=jwt-bearer, requested_token_use=on_behalf_of
       v
  OBO token   (aud = Advisory API,     sub/oid = SAME user, appid = Orchestrator)
"""

from __future__ import annotations

import os
import sys
import uuid

import httpx
import uvicorn

from a2a.helpers.proto_helpers import new_task_from_user_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import AgentSkill, Part

from agent_common import IDENTITY_EXTENSION_URI, create_app, create_card, record, token_view
from entra_auth import EntraConfigError, PassthroughValidator

AGENT_LABEL = "orchestrator"


def collect_text(node) -> list[str]:
    """Gather every `text` value from an A2A response, whatever its exact shape."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "text" and isinstance(value, str):
                found.append(value)
            else:
                found.extend(collect_text(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(collect_text(item))
    return found


IDENTITY = {
    "name": "Orchestrator Agent",
    "role": "Exchanges the user token (OBO) and delegates to the Advisory Agent",
    "model": "rule-based",
    "version": "1.0.0",
}


class OboConfig:
    def __init__(self) -> None:
        env = os.environ.get
        self.tenant = env("ENTRA_TENANT_ID", "").strip()
        self.client_id = env("ORCH_CLIENT_ID", "").strip()
        self.client_secret = env("ORCH_CLIENT_SECRET", "").strip()
        audience = env("OBO_TOKEN_AUDIENCE", "").strip()
        scope_name = env("OBO_TOKEN_SCOPE", "").strip()
        self.scope = f"{audience}/{scope_name}"
        # Gateway URL wins when set (Phase 2); otherwise call the advisory agent directly.
        self.advisory_url = (
            env("ADVISORY_GATEWAY_URL", "").strip() or env("ADVISORY_PUBLIC_URL", "").strip()
        ).rstrip("/")
        missing = [
            name
            for name, value in {
                "ENTRA_TENANT_ID": self.tenant,
                "ORCH_CLIENT_ID": self.client_id,
                "ORCH_CLIENT_SECRET": self.client_secret,
                "OBO_TOKEN_AUDIENCE": audience,
                "OBO_TOKEN_SCOPE": scope_name,
                "ADVISORY_GATEWAY_URL or ADVISORY_PUBLIC_URL": self.advisory_url,
            }.items()
            if not value
        ]
        if missing:
            raise EntraConfigError(f"Missing in .env: {', '.join(missing)}")
        self.token_endpoint = (
            f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token"
        )


async def exchange_on_behalf_of(config: OboConfig, user_token: str) -> str:
    """Trade the user's token for a token for the Advisory API (Entra OBO)."""
    form = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "requested_token_use": "on_behalf_of",
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "assertion": user_token,
        "scope": config.scope,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(config.token_endpoint, data=form)
    request_view = {
        "url": config.token_endpoint,
        "grant_type": form["grant_type"],
        "requested_token_use": "on_behalf_of",
        "client_id": config.client_id,
        "scope": config.scope,
        "assertion": "<user token>",
        "client_secret": "<redacted>",
    }
    if response.status_code != 200:
        record(
            "obo_failed",
            agent=AGENT_LABEL,
            request=request_view,
            status=response.status_code,
            error=response.text,
        )
        raise RuntimeError(f"Entra OBO exchange failed (HTTP {response.status_code}): {response.text}")
    obo_token = response.json()["access_token"]
    record(
        "obo_exchange",
        agent=AGENT_LABEL,
        request=request_view,
        status=200,
        obo_token=token_view(obo_token),
    )
    return obo_token


async def call_advisory(config: OboConfig, obo_token: str, question: str) -> tuple[int, str]:
    payload = {
        "jsonrpc": "2.0",
        "id": uuid.uuid4().hex[:8],
        "method": "SendMessage",
        "params": {
            "message": {
                "messageId": uuid.uuid4().hex,
                "role": "ROLE_USER",
                "parts": [{"text": question}],
            }
        },
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            config.advisory_url,
            json=payload,
            headers={
                "Authorization": f"Bearer {obo_token}",
                "Content-Type": "application/json",
                "A2A-Version": "1.0",
            },
        )
    try:
        text = " ".join(collect_text(response.json().get("result", {}))) or response.text
    except ValueError:
        text = response.text
    record(
        "advisory_call",
        agent=AGENT_LABEL,
        url=config.advisory_url,
        status=response.status_code,
        response=text,
    )
    return response.status_code, text


class OrchestratorExecutor(AgentExecutor):
    def __init__(self, config: OboConfig) -> None:
        self._config = config

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if context.current_task is None:
            await event_queue.enqueue_event(new_task_from_user_message(context.message))
        await updater.start_work()

        state = context.call_context.state if context.call_context else {}
        user_token = state.get("token", "")
        record("user_token", agent=AGENT_LABEL, user_token=token_view(user_token))

        try:
            obo_token = await exchange_on_behalf_of(self._config, user_token)
            status, advice = await call_advisory(self._config, obo_token, context.get_user_input())
            text = advice if status == 200 else f"Advisory Agent returned HTTP {status}: {advice}"
        except Exception as error:  # noqa: BLE001 - raw error is returned to the caller
            text = str(error)
        reply = updater.new_agent_message([Part(text=text)], metadata={IDENTITY_EXTENSION_URI: IDENTITY})
        reply.extensions.append(IDENTITY_EXTENSION_URI)
        await updater.complete(reply)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await TaskUpdater(event_queue, context.task_id, context.context_id).cancel()


def build_app(port: int):
    config = OboConfig()
    validator = PassthroughValidator()
    base_url = os.environ.get("ORCH_PUBLIC_URL", f"http://localhost:{port}").rstrip("/")
    card = create_card(
        name="Orchestrator Agent",
        description="Receives a signed-in user's token and acts on the user's behalf (Entra OBO) "
        "when calling the Security Advisory Agent.",
        base_url=base_url,
        skill=AgentSkill(
            id="ask-advisor",
            name="Ask the security advisor",
            description="Forwards the question to the Advisory Agent using an OBO token.",
            tags=["orchestrator", "obo"],
            examples=["How do I spot phishing?"],
        ),
        scheme_note="Entra user access token (aud = Orchestrator API, scp = agent.access).",
        identity=IDENTITY,
    )
    return create_app(
        card=card,
        executor=OrchestratorExecutor(config),
        validator=validator,
        agent_label=AGENT_LABEL,
    )


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 10003
    try:
        app = build_app(port)
    except EntraConfigError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    uvicorn.run(app, host="0.0.0.0", port=port)
