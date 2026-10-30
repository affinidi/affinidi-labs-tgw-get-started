#!/usr/bin/env python3
"""Personal Agent - an A2A v1.0 agent that uses the GitHub MCP server through an
Agent Gateway surface with credential delegation.

  Portal --(A2A, Entra user token)--> Gateway agent access point
  Gateway: validates the Entra token, then calls the agent with X-Transit-Token
  Agent --(MCP, X-Transit-Token)--> Gateway GitHub MCP transit point
  Gateway: looks up the caller's delegated GitHub OAuth token
           - none yet  -> 401 consent_required + GitHub authorization URL
           - has token -> injects it and forwards to api.githubcopilot.com/mcp

The agent never sees a GitHub credential. When the gateway asks for consent,
the task ends in TASK_STATE_AUTH_REQUIRED and carries the authorization URL in
its status message metadata; the user approves and resends the prompt.
"""

from __future__ import annotations

import json
import os
import re
import sys

import uvicorn

from a2a.helpers.proto_helpers import new_task_from_user_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import AgentSkill, Part

from agent_common import IDENTITY_EXTENSION_URI, create_app, create_card, record
from entra_auth import EntraConfigError, EntraTokenValidator, PassthroughValidator, load_settings
from mcp_gateway_client import GatewayError, McpGatewayClient

AGENT_LABEL = "delegate-agent"
AGENT_NAME = os.environ.get("AGENT_NAME", "").strip() or "Personal Agent"
CONSENT_METADATA_KEY = "consent_required"
# Raw upstream (gateway / MCP server / Entra) response, passed through to the portal.
UPSTREAM_ERROR_KEY = "upstream_error"
REPO_PATTERN = re.compile(r"\b([A-Za-z0-9-]{1,39})/([A-Za-z0-9._-]{1,100})\b")

IDENTITY = {
    "name": AGENT_NAME,
    "role": "Answers questions about the user's GitHub account via the GitHub MCP server",
    "model": "rule-based",
    "version": "1.0.0",
}

HELP_TEXT = (
    "I can work with GitHub on your behalf. Try:\n"
    "- Who am I on GitHub?\n"
    "- List my repositories\n"
    "- What GitHub tools can you use?\n"
    "- Show my GitHub projects\n"
    "- Show my notifications"
)

GREETING_PATTERN = re.compile(
    r"^\s*(say\s+)?(hi|hello|hey|hiya|good (morning|afternoon|evening))\b", re.I
)


def greeting_reply(user: str) -> str:
    name = "" if user in ("", "unknown") else f" {user}"
    return f"Hi{name}! How can I help you with GitHub today?"


class AgentConfig:
    def __init__(self) -> None:
        gateway_url = os.environ.get("MCP_GATEWAY_URL", "").strip()
        self.via_gateway = bool(gateway_url)
        self.mcp_url = gateway_url or os.environ.get("MCP_URL", "").strip()
        if not self.mcp_url.lower().startswith("https://"):
            raise EntraConfigError("Set MCP_GATEWAY_URL or MCP_URL to an https MCP endpoint")


# --- intent -> MCP tool -------------------------------------------------------


def plan(text: str) -> tuple[str, dict] | None:
    """Map a prompt to a (tool, arguments) pair. Rule-based, no LLM."""
    lowered = text.lower()
    if "tool" in lowered:
        return ("__list_tools__", {})
    if "team" in lowered:
        return ("get_teams", {})
    if "gist" in lowered:
        return ("list_gists", {"perPage": 10})
    if "notification" in lowered:
        return ("list_notifications", {"perPage": 10})
    if "project" in lowered:
        return ("__my_projects__", {})
    match = REPO_PATTERN.search(text)
    if match and "dependabot" in lowered:
        return ("list_dependabot_alerts", {"owner": match[1], "repo": match[2], "perPage": 10})
    if match and "create" in lowered and "issue" in lowered:
        return (
            "issue_write",
            {
                "method": "create",
                "owner": match[1],
                "repo": match[2],
                "title": "Created by the A2A GitHub agent lab",
            },
        )
    if match:
        if "issue" in lowered:
            return ("list_issues", {"owner": match[1], "repo": match[2], "state": "OPEN", "perPage": 10})
        if "pull" in lowered or re.search(r"\bprs?\b", lowered):
            return ("list_pull_requests", {"owner": match[1], "repo": match[2], "state": "open", "perPage": 10})
    if "pull request" in lowered or re.search(r"\bprs?\b", lowered):
        return ("search_pull_requests", {"query": "is:open author:@me", "perPage": 10})
    if "issue" in lowered:
        return ("search_issues", {"query": "is:open assignee:@me", "perPage": 10})
    if "repo" in lowered:
        return ("__my_repos__", {})
    if any(k in lowered for k in ("who am i", "profile", "me on github", "my account")):
        return ("get_me", {})
    return None


def tool_text(result: dict) -> str:
    return "\n".join(
        item.get("text", "") for item in result.get("content", []) if item.get("type") == "text"
    )


def tool_json(result: dict):
    if isinstance(result.get("structuredContent"), (dict, list)):
        return result["structuredContent"]
    try:
        return json.loads(tool_text(result))
    except ValueError:
        return None


def _items(data) -> list[dict]:
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        for key in ("items", "issues", "pullRequests", "pull_requests", "repositories", "teams", "projects", "nodes"):
            if isinstance(data.get(key), list):
                return _items(data[key])
    return []


def format_items(title: str, data, empty: str) -> str:
    items = _items(data)
    if not items:
        return empty
    total = data.get("total_count") if isinstance(data, dict) else None
    lines = [f"{title}" + (f" ({total} total)" if isinstance(total, int) else "")]
    for item in items[:10]:
        label = item.get("full_name") or item.get("title") or item.get("name") or item.get("login") or "?"
        if item.get("number"):
            label = f"#{item['number']} {label}"
        extras = []
        if "stargazers_count" in item:
            extras.append(f"★ {item['stargazers_count']}")
        if item.get("private") is True:
            extras.append("private")
        if isinstance(item.get("state"), str):
            extras.append(item["state"].lower())
        line = f"- {label}" + (f" ({', '.join(extras)})" if extras else "")
        if url := item.get("html_url") or item.get("url"):
            line += f"\n  {url}"
        lines.append(line)
    return "\n".join(lines)


def format_profile(data) -> str:
    if not isinstance(data, dict):
        return "GitHub returned an empty profile."
    details = data.get("details") if isinstance(data.get("details"), dict) else {}
    merged = {**details, **data}
    fields = [
        ("Login", merged.get("login")),
        ("Name", merged.get("name")),
        ("Company", merged.get("company")),
        ("Public repos", merged.get("public_repos")),
        ("Followers", merged.get("followers")),
        ("Profile", merged.get("profile_url") or merged.get("html_url")),
    ]
    lines = [f"- {label}: {value}" for label, value in fields if value not in (None, "")]
    return "Your GitHub profile (via the gateway's delegated token):\n" + "\n".join(lines)


async def run_plan(mcp: McpGatewayClient, tool: str, args: dict) -> tuple[str, list[str]]:
    """Execute the plan; returns (reply text, MCP tools called)."""
    if tool == "__list_tools__":
        tools = await mcp.list_tools()
        names = sorted(t.get("name", "?") for t in tools)
        return (
            f"The GitHub MCP server exposes {len(names)} tools through this surface:\n"
            + "\n".join(f"- {n}" for n in names),
            ["tools/list"],
        )
    if tool == "__my_repos__":
        me = tool_json(await mcp.call_tool("get_me"))
        login = (me or {}).get("login") if isinstance(me, dict) else None
        if not login:
            return "Could not determine your GitHub login.", ["get_me"]
        result = await mcp.call_tool(
            "search_repositories", {"query": f"user:{login} sort:updated", "perPage": 10}
        )
        return _render("search_repositories", result, f"Repositories for {login}"), [
            "get_me",
            "search_repositories",
        ]
    if tool == "__my_projects__":
        me = tool_json(await mcp.call_tool("get_me"))
        login = (me or {}).get("login") if isinstance(me, dict) else None
        if not login:
            return "Could not determine your GitHub login.", ["get_me"]
        result = await mcp.call_tool(
            "projects_list",
            {"method": "list_projects", "owner": login, "owner_type": "user", "perPage": 10},
        )
        return _render("projects_list", result, f"Projects for {login}"), [
            "get_me",
            "projects_list",
        ]
    result = await mcp.call_tool(tool, args)
    titles = {
        "get_teams": "Your teams",
        "list_gists": "Your gists",
        "list_notifications": "Your notifications",
        "list_dependabot_alerts": f"Dependabot alerts in {args.get('owner')}/{args.get('repo')}",
        "issue_write": f"Issue created in {args.get('owner')}/{args.get('repo')}",
        "get_me": "",
        "search_pull_requests": "Your open pull requests",
        "search_issues": "Open issues assigned to you",
        "list_issues": f"Open issues in {args.get('owner')}/{args.get('repo')}",
        "list_pull_requests": f"Open pull requests in {args.get('owner')}/{args.get('repo')}",
    }
    return _render(tool, result, titles.get(tool, tool)), [tool]


def _render(tool: str, result: dict, title: str) -> str:
    if result.get("isError"):
        return f"GitHub tool '{tool}' failed: {tool_text(result)[:1000]}"
    data = tool_json(result)
    if tool == "get_me":
        return format_profile(data)
    if data is None:
        return tool_text(result)[:3000] or "No result."
    return format_items(title, data, f"{title}: nothing found.")


# --- A2A executor -------------------------------------------------------------


class GitHubAgentExecutor(AgentExecutor):
    def __init__(self, config: AgentConfig) -> None:
        self._config = config

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if context.current_task is None:
            await event_queue.enqueue_event(new_task_from_user_message(context.message))
        await updater.start_work()

        state = context.call_context.state if context.call_context else {}
        transit_token = state.get("transit_token", "")
        claims = state.get("claims", {})
        user = claims.get("name") or claims.get("preferred_username") or claims.get("oid", "unknown")
        prompt = context.get_user_input().strip()
        record("prompt", agent=AGENT_LABEL, user=user, prompt=prompt)

        def reply(text: str, metadata: dict | None = None):
            message = updater.new_agent_message(
                [Part(text=text)],
                metadata={IDENTITY_EXTENSION_URI: IDENTITY, **(metadata or {})},
            )
            message.extensions.append(IDENTITY_EXTENSION_URI)
            return message

        if GREETING_PATTERN.match(prompt):
            record("plan", agent=AGENT_LABEL, tool=None, note="greeting, answered locally")
            await updater.complete(reply(greeting_reply(user)))
            return
        step = plan(prompt)
        if step is None:
            await updater.complete(reply(HELP_TEXT))
            return
        tool, args = step
        record("plan", agent=AGENT_LABEL, tool=tool, arguments=args)

        def on_exchange(event: dict) -> None:
            record("mcp_call", agent=AGENT_LABEL, **event)

        try:
            # Hand the gateway's transit token back to the GitHub transit point, which
            # does the credential delegation. No token -> the gateway's own error is relayed.
            record("route", agent=AGENT_LABEL, url=self._config.mcp_url,
                   via="gateway" if self._config.via_gateway else "direct",
                   transit_token_present=bool(transit_token))
            async with McpGatewayClient(
                self._config.mcp_url,
                transit_token=transit_token, via_gateway=self._config.via_gateway,
                on_exchange=on_exchange,
            ) as mcp:
                text, called = await run_plan(mcp, tool, args)
            record("completed", agent=AGENT_LABEL, tools=called)
            await updater.complete(reply(text, {"mcp_tools": called}))
        except GatewayError as error:
            raw = error.raw()
            if error.consent_required:
                consent = [c.as_dict() for c in error.consent]
                record("consent_required", agent=AGENT_LABEL, consent=consent, upstream=raw)
                await updater.requires_auth(
                    reply(
                        "GitHub authorization is required. Open the authorization link, "
                        "approve access for the gateway, then send your request again.",
                        {CONSENT_METADATA_KEY: consent, UPSTREAM_ERROR_KEY: raw},
                    )
                )
                return
            record("failed", agent=AGENT_LABEL, status=error.status, error=str(error), upstream=raw)
            await updater.failed(reply(str(error), {UPSTREAM_ERROR_KEY: raw}))
        except Exception as error:  # noqa: BLE001 - surface unexpected agent bugs to the portal
            raw = {"source": "agent", "exception": type(error).__name__, "message": str(error)}
            record("failed", agent=AGENT_LABEL, error=f"{type(error).__name__}: {error}", upstream=raw)
            await updater.failed(
                reply(f"Agent error: {type(error).__name__}: {error}", {UPSTREAM_ERROR_KEY: raw})
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await TaskUpdater(event_queue, context.task_id, context.context_id).cancel()


def build_app(port: int):
    config = AgentConfig()
    # Default: no validation here - the gateway is the single enforcement point and
    # its 401/consent errors are relayed verbatim. Set AGENT_VALIDATE_TOKEN=true to
    # also validate the Entra token at the agent (defense in depth).
    if os.environ.get("AGENT_VALIDATE_TOKEN", "false").strip().lower() == "true":
        validator = EntraTokenValidator(load_settings("USER_TOKEN_AUDIENCE", "USER_TOKEN_SCOPE"))
    else:
        validator = PassthroughValidator()
        print(f"[{AGENT_LABEL}] token validation disabled - gateway enforces auth", flush=True)
    base_url = os.environ.get("AGENT_PUBLIC_URL", f"http://localhost:{port}").rstrip("/")
    card = create_card(
        name=AGENT_NAME,
        description="Works with GitHub on behalf of a signed-in user through the GitHub MCP "
        "server, reached via an Agent Gateway surface that holds the user's delegated "
        "GitHub OAuth token.",
        base_url=base_url,
        skill=AgentSkill(
            id="github",
            name="GitHub on your behalf",
            description="Profile, repositories, pull requests and issues via GitHub MCP.",
            tags=["github", "mcp", "credential-delegation"],
            examples=[
                "Who am I on GitHub?",
                "List my repositories",
                "Show my open pull requests",
                "Show issues assigned to me",
            ],
        ),
        scheme_note="Entra user access token (aud = USER_TOKEN_AUDIENCE, scp = USER_TOKEN_SCOPE).",
        identity=IDENTITY,
    )
    return create_app(
        card=card,
        executor=GitHubAgentExecutor(config),
        validator=validator,
        agent_label=AGENT_LABEL,
    )


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 10004
    try:
        app = build_app(port)
    except EntraConfigError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    uvicorn.run(app, host="0.0.0.0", port=port)
