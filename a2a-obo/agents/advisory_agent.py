#!/usr/bin/env python3
"""Advisory Agent - the downstream agent that receives the OBO token.

It accepts a call only if the bearer token carries the OBO scope (`scp`). It does
NOT verify the signature, issuer, audience or caller: token validation is left to
the gateway (Phase 2). The token's `oid`/`name` identify the human the Orchestrator
is acting for.
"""

from __future__ import annotations

import os
import sys

import uvicorn

from a2a.helpers.proto_helpers import new_task_from_user_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import AgentSkill, Part

from agent_common import IDENTITY_EXTENSION_URI, create_app, create_card, record
from entra_auth import (
    EntraConfigError,
    EntraTokenValidator,
    TokenError,
    decode_unverified,
)

AGENT_LABEL = "advisory"

ADVICE = {
    "phishing": "Enable MFA, report the message, and never enter credentials from an emailed link.",
    "password": "Use a password manager, unique 14+ character passwords, and MFA everywhere.",
    "laptop": "Keep full-disk encryption on, apply updates within 7 days, and lock when away.",
}
DEFAULT_ADVICE = "Follow least privilege, patch promptly, and report anything suspicious to security."


IDENTITY = {
    "name": "Security Advisory Agent",
    "role": "Answers security-hygiene questions for a user (OBO scope required)",
    "model": "rule-based",
    "version": "1.0.0",
}


class AdvisoryExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if context.current_task is None:
            await event_queue.enqueue_event(new_task_from_user_message(context.message))
        await updater.start_work()

        claims = context.call_context.state.get("claims", {}) if context.call_context else {}
        question = context.get_user_input()
        advice = next((a for k, a in ADVICE.items() if k in question.lower()), DEFAULT_ADVICE)
        user = claims.get("name") or claims.get("preferred_username") or claims.get("oid", "unknown")
        agent = claims.get("appid", "unknown")

        record("advice", agent=AGENT_LABEL, user=user, acting_agent=agent, question=question)
        text = (
            f"Security advice for {user} (acting agent app: {agent}): {advice}"
        )
        reply = updater.new_agent_message([Part(text=text)], metadata={IDENTITY_EXTENSION_URI: IDENTITY})
        reply.extensions.append(IDENTITY_EXTENSION_URI)
        await updater.complete(reply)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await TaskUpdater(event_queue, context.task_id, context.context_id).cancel()


class ScopeOnlyValidator:
    """Reads the OBO token's claims without verifying signature, issuer, audience or expiry.

    The only decision it makes is on `scp`. Lab simplification: it is safe only when
    something upstream (the gateway in Phase 2) has already validated the token.
    """

    extract_bearer = staticmethod(EntraTokenValidator.extract_bearer)

    def __init__(self, required_scope: str) -> None:
        self.required_scope = required_scope

    def validate(self, token: str) -> dict:
        claims = decode_unverified(token)
        if not claims:
            raise TokenError("invalid_token", "Token could not be decoded.")
        if self.required_scope not in str(claims.get("scp", "")).split():
            raise TokenError(
                "insufficient_scope",
                f"Token does not grant scope '{self.required_scope}'.",
            )
        return claims


def build_app(port: int):
    scope = os.environ.get("OBO_TOKEN_SCOPE", "").strip()
    if not scope:
        raise EntraConfigError("OBO_TOKEN_SCOPE must be set in .env")
    validator = ScopeOnlyValidator(scope)
    base_url = os.environ.get("ADVISORY_PUBLIC_URL", f"http://localhost:{port}").rstrip("/")
    card = create_card(
        name="Security Advisory Agent",
        description="Answers security-hygiene questions on behalf of an authenticated user. "
        "Requires the OBO scope on the token.",
        base_url=base_url,
        skill=AgentSkill(
            id="security-advice",
            name="Security advice",
            description="Short security guidance for the signed-in user.",
            tags=["advisory", "obo"],
            examples=["How do I spot phishing?"],
        ),
        scheme_note="Entra OBO access token (scp = OBO scope).",
        identity=IDENTITY,
    )
    return create_app(
        card=card, executor=AdvisoryExecutor(), validator=validator, agent_label=AGENT_LABEL
    )


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 10002
    try:
        app = build_app(port)
    except EntraConfigError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    uvicorn.run(app, host="0.0.0.0", port=port)
