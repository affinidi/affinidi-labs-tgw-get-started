#!/usr/bin/env python3
"""Minimal MCP (Streamable HTTP) client that talks to the GitHub MCP server
through an Agent Gateway surface.

It is hand-rolled on httpx rather than the MCP SDK on purpose: the gateway
answers a missing delegated credential with an HTTP error carrying a
`consent_required` problem document, and the agent needs that body intact to
hand the authorization URL back to the user.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

# First version offered on initialize. The gateway surface accepts 2024-11-05 and
# 2026-07-28; other versions get a -32022 and are renegotiated below.
MCP_PROTOCOL_VERSION = os.environ.get("MCP_PROTOCOL_VERSION", "2024-11-05").strip() or "2024-11-05"
# Versions this client can speak, most preferred first. The gateway may only
# accept a subset (it answers -32022 with `data.supported`), so we renegotiate.
KNOWN_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
UNSUPPORTED_PROTOCOL_VERSION = -32022
MAX_TRACE_BODY = 6000


def _negotiate_version(error: "GatewayError") -> str | None:
    body = error.body if isinstance(error.body, dict) else {}
    if isinstance(body.get("error"), dict):
        body = body["error"]
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    if body.get("code") != UNSUPPORTED_PROTOCOL_VERSION:
        return None
    supported = [v for v in data.get("supported", []) if isinstance(v, str)]
    for version in KNOWN_PROTOCOL_VERSIONS:
        if version in supported:
            return version
    return max(supported) if supported else None


@dataclass
class ConsentRequest:
    provider: str
    authorization_url: str
    scopes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "provider_name": self.provider,
            "authorization_url": self.authorization_url,
            "scopes": self.scopes,
        }


class GatewayError(Exception):
    """A non-success answer from the gateway or the MCP server behind it."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        body: Any = None,
        consent: list[ConsentRequest] | None = None,
        needs_consent: bool = False,
        source: str = "gateway",
        method: str | None = None,
        url: str | None = None,
        headers: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
        self.consent = consent or []
        self._needs_consent = needs_consent
        self.source = source
        self.method = method
        self.url = url
        self.headers = headers or {}

    @property
    def consent_required(self) -> bool:
        return self._needs_consent or bool(self.consent)

    def raw(self) -> dict:
        """The upstream response exactly as received (secrets redacted), for display."""
        return {
            "source": self.source,
            "method": self.method,
            "url": self.url,
            "http_status": self.status,
            "headers": self.headers,
            "body": self.body,
            "message": str(self),
        }


def _find_consent(payload: Any) -> list[ConsentRequest]:
    """Pull consent requests out of a problem+json body or a JSON-RPC error.

    Only https authorization URLs are accepted: the URL is shown to the user as
    a link, so anything else is dropped rather than rendered.
    """
    candidates: list[Any] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            value = node.get("consent_required")
            if isinstance(value, list):
                candidates.extend(value)
            for child in node.values():
                if isinstance(child, (dict, list)):
                    walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(payload)
    found: list[ConsentRequest] = []
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        url = entry.get("authorization_url")
        if not isinstance(url, str) or not url.lower().startswith("https://"):
            continue
        scopes = entry.get("scopes")
        found.append(
            ConsentRequest(
                provider=str(entry.get("provider_name") or "GitHub"),
                authorization_url=url,
                scopes=[str(s) for s in scopes] if isinstance(scopes, list) else [],
            )
        )
    return found


def _looks_like_consent(payload: Any) -> bool:
    return isinstance(payload, dict) and bool(
        re.search(r"consent[-_]required", str(payload.get("type", "")), re.I)
    )


def _parse_body(response: httpx.Response) -> Any:
    """Decode a JSON or SSE (text/event-stream) MCP response."""
    content_type = response.headers.get("content-type", "")
    text = response.text
    if "text/event-stream" in content_type:
        messages = []
        for block in text.split("\n\n"):
            data = "\n".join(
                line[5:].lstrip() for line in block.splitlines() if line.startswith("data:")
            )
            if data:
                try:
                    messages.append(json.loads(data))
                except ValueError:
                    continue
        return messages[-1] if len(messages) == 1 else messages
    if not text:
        return None
    try:
        return response.json()
    except ValueError:
        return {"raw": text[:MAX_TRACE_BODY]}


def _pick_reply(body: Any, request_id: str) -> Any:
    if isinstance(body, list):
        for message in body:
            if isinstance(message, dict) and message.get("id") == request_id:
                return message
        return body[-1] if body else None
    return body


def _safe_headers(headers: httpx.Headers | dict) -> dict:
    return {
        key: (
            "<redacted>"
            if key.lower() in {"authorization", "cookie", "set-cookie", "x-transit-token"}
            else value
        )
        for key, value in dict(headers).items()
    }


def _trim(value: Any) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= MAX_TRACE_BODY else text[:MAX_TRACE_BODY] + "…truncated…"


class McpGatewayClient:
    """One MCP session against the gateway surface, for a single A2A task."""

    def __init__(
        self,
        url: str,
        bearer_token: str = "",
        *,
        transit_token: str = "",
        via_gateway: bool = True,
        on_exchange: Callable[[dict], None] | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._url = url
        self._token = bearer_token
        self._transit_token = transit_token
        self._via_gateway = via_gateway
        self._on_exchange = on_exchange or (lambda _event: None)
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._session_id: str | None = None
        self._protocol_version = MCP_PROTOCOL_VERSION
        self.server_info: dict = {}

    async def __aenter__(self) -> "McpGatewayClient":
        self._client = httpx.AsyncClient(timeout=self._timeout)
        try:
            try:
                result = await self._initialize(MCP_PROTOCOL_VERSION)
            except GatewayError as error:
                fallback = _negotiate_version(error)
                if not fallback or fallback == MCP_PROTOCOL_VERSION:
                    raise
                result = await self._initialize(fallback)
            if not isinstance(result, dict):
                raise GatewayError("MCP initialize returned no result.", body=result)
            self._protocol_version = result.get("protocolVersion", self._protocol_version)
            self.server_info = result.get("serverInfo", {}) or {}
            await self._rpc("notifications/initialized", None, notification=True)
        except BaseException:
            await self._client.aclose()
            raise
        return self

    async def _initialize(self, version: str) -> Any:
        self._protocol_version = version
        self._session_id = None
        return await self._rpc(
            "initialize",
            {
                "protocolVersion": version,
                "capabilities": {},
                "clientInfo": {"name": "github-mcp-a2a-agent", "version": "1.0.0"},
            },
        )

    async def __aexit__(self, *_exc) -> None:
        if self._client is None:
            return
        if self._session_id:
            try:
                await self._client.delete(self._url, headers=self._headers())
            except httpx.HTTPError:
                pass
        await self._client.aclose()

    async def list_tools(self) -> list[dict]:
        result = await self._rpc("tools/list", {})
        return result.get("tools", []) if isinstance(result, dict) else []

    async def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        result = await self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        if not isinstance(result, dict):
            raise GatewayError(f"Tool '{name}' returned no result.", body=result)
        return result

    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self._protocol_version,
        }
        # No token -> no header, so the gateway answers with its own 401.
        if self._token:
            headers["Authorization"] = "Bearer " + self._token
        if self._transit_token:
            headers["X-Transit-Token"] = self._transit_token
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    async def _rpc(self, method: str, params: dict | None, *, notification: bool = False) -> Any:
        assert self._client is not None
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        request_id = None
        if not notification:
            request_id = uuid.uuid4().hex[:12]
            message["id"] = request_id

        headers = self._headers()
        context = {"method": method, "url": self._url}
        try:
            response = await self._client.post(self._url, json=message, headers=headers)
        except httpx.HTTPError as error:
            self._on_exchange(
                {"method": method, "url": self._url, "request": message, "error": str(error)}
            )
            raise GatewayError(
                f"Gateway unreachable: {error!r}",
                source="network",
                body={"exception": type(error).__name__, "detail": str(error)},
                **context,
            ) from error

        if session_id := response.headers.get("mcp-session-id"):
            self._session_id = session_id

        body = _parse_body(response)
        context.update(status=response.status_code, headers=_safe_headers(response.headers))
        self._on_exchange(
            {
                "method": method,
                "url": self._url,
                "request": {"headers": _safe_headers(headers), "body": message},
                "response": {
                    "status": response.status_code,
                    "headers": _safe_headers(response.headers),
                    "body": _trim(body),
                },
            }
        )

        if response.status_code >= 400:
            consent = _find_consent(body)
            if consent or _looks_like_consent(body):
                raise GatewayError(
                    "The gateway needs your consent before it can call GitHub for you.",
                    body=body,
                    consent=consent,
                    needs_consent=True,
                    **context,
                )
            detail = ""
            challenge = response.headers.get("www-authenticate", "")
            if scope_match := re.search(r'error="insufficient_scope".*?scope="([^"]+)"', challenge):
                detail = f"GitHub token is missing OAuth scope(s): {scope_match[1]}"
            if isinstance(body, dict) and not detail:
                inner = body.get("error")
                detail = str(
                    body.get("detail")
                    or body.get("title")
                    or (inner.get("message") if isinstance(inner, dict) else inner)
                    or ""
                )
            raise GatewayError(
                f"{'Gateway' if self._via_gateway else 'MCP server'} returned "
                f"HTTP {response.status_code} on MCP {method}"
                + (f": {detail}" if detail else ""),
                body=body,
                source="gateway" if self._via_gateway else "mcp_server",
                **context,
            )

        if notification:
            return None

        reply = _pick_reply(body, request_id or "")
        if not isinstance(reply, dict):
            raise GatewayError(
                f"Unexpected MCP response to {method}.", source="mcp", body=body, **context
            )
        if reply.get("error"):
            error = reply["error"]
            consent = _find_consent(error)
            raise GatewayError(
                f"MCP error on {method}: "
                f"{error.get('message', error) if isinstance(error, dict) else error}",
                source="mcp",
                body=reply,
                consent=consent,
                **context,
            )
        result = reply.get("result", {})
        if isinstance(result, dict) and result.get("isError"):
            text = "\n".join(
                str(c.get("text", "")) for c in result.get("content", []) if isinstance(c, dict)
            ).strip()
            raise GatewayError(
                f"MCP tool error on {method}: {text[:500] or 'isError=true'}",
                source="mcp_tool",
                body=reply,
                consent=_find_consent(result),
                **context,
            )
        return result
