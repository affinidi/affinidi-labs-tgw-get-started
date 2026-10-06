#!/usr/bin/env python3
"""
MCP Test Client (Streamable HTTP transport, protocol version 2026-07-28)

Talks to the mcp-latest server's single /mcp endpoint. Revision 2026-07-28
has no `initialize` handshake and no sessions — every request is stateless
and carries its own protocol version + method/name metadata:
- `params._meta["io.modelcontextprotocol/protocolVersion"]` plus the mirrored
  `MCP-Protocol-Version` HTTP header
- `Mcp-Method` header mirroring `method`
- `Mcp-Name` header mirroring `params.name` for tools/call (and
  resources/read, prompts/get)
"""

import json
import sys
from typing import Any, Dict, Optional

import requests

PROTOCOL_VERSION = "2026-07-28"
META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CLIENT_INFO = "io.modelcontextprotocol/clientInfo"
META_CLIENT_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"


class MCPClient:
    """Stateless Streamable HTTP MCP client for testing"""

    def __init__(self, base_url: str = "http://localhost:11100", client_info: Optional[Dict] = None, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.mcp_url = f"{self.base_url}/mcp"
        self.request_id = 0
        self.client_info = client_info or {
            "name": "MCP Test Client", "version": "3.0.0"}
        self.api_key = api_key

    def _get_next_id(self) -> int:
        self.request_id += 1
        return self.request_id

    def _headers(self, method: str, name: Optional[str] = None, protocol_version: str = PROTOCOL_VERSION) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": protocol_version,
            "Mcp-Method": method
        }
        if name is not None:
            headers["Mcp-Name"] = name
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _send_request(self, method: str, params: Optional[Dict] = None, name: Optional[str] = None,
                      protocol_version: str = PROTOCOL_VERSION, header_overrides: Optional[Dict] = None) -> requests.Response:
        request_id = self._get_next_id()
        params = params or {}
        params["_meta"] = {
            META_PROTOCOL_VERSION: protocol_version,
            META_CLIENT_INFO: self.client_info,
            META_CLIENT_CAPABILITIES: {}
        }
        payload = {"jsonrpc": "2.0", "id": request_id,
                   "method": method, "params": params}

        headers = self._headers(method, name, protocol_version)
        if header_overrides:
            headers.update(header_overrides)

        print(f"\n{'='*60}")
        print(f"Request: {method} (id={request_id})")
        print(f"{'='*60}")
        print(json.dumps(payload, indent=2))

        response = requests.post(self.mcp_url, json=payload, headers=headers)

        print(f"\n{'='*60}")
        print(
            f"Response: {method} (id={request_id}) — HTTP {response.status_code}")
        print(f"{'='*60}")
        if response.content:
            try:
                print(json.dumps(response.json(), indent=2))
            except Exception:
                print(response.text)

        return response

    def discover(self) -> Dict:
        response = self._send_request("server/discover")
        response.raise_for_status()
        return response.json()

    def list_tools(self) -> Dict:
        response = self._send_request("tools/list")
        response.raise_for_status()
        return response.json()

    def call_tool(self, name: str, arguments: Dict) -> Dict:
        response = self._send_request(
            "tools/call", {"name": name, "arguments": arguments}, name=name)
        response.raise_for_status()
        return response.json()


def run_test_suite(client: MCPClient):
    print("\n" + "=" * 60)
    print("MCP Streamable HTTP Test Suite (protocol 2026-07-28, stateless)")
    print("=" * 60)

    print("\n\n[TEST 1] server/discover")
    result = client.discover()
    assert result.get("result"), "discover failed"
    assert PROTOCOL_VERSION in result["result"].get("supportedVersions", [])
    print("✅ server/discover: PASSED")

    print("\n\n[TEST 2] List Tools")
    result = client.list_tools()
    assert result.get("result"), "List tools failed"
    tools = result["result"].get("tools", [])
    assert len(tools) == 2, f"Expected 2 tools, got {len(tools)}"
    print(f"✅ List Tools: PASSED ({len(tools)} tools)")

    print("\n\n[TEST 3] Calculator: Addition")
    result = client.call_tool(
        "calculator", {"operation": "add", "a": 15, "b": 27})
    assert result.get("result"), "Call tool failed"
    assert result["result"]["structuredContent"]["result"] == 42
    print("✅ Calculator Addition: PASSED")

    print("\n\n[TEST 4] Calculator: Division")
    result = client.call_tool(
        "calculator", {"operation": "divide", "a": 144, "b": 12})
    assert result.get("result"), "Call tool failed"
    assert result["result"]["structuredContent"]["result"] == 12
    print("✅ Calculator Division: PASSED")

    print("\n\n[TEST 5] Weather Forecast: Multiple Days")
    result = client.call_tool(
        "weather_forecast", {"city": "New York", "days": 3})
    assert result.get("result"), "Call tool failed"
    structured = result["result"]["structuredContent"]
    assert structured["city"] == "New York" and len(
        structured["forecast"]) == 3
    print("✅ Weather Multiple Days: PASSED")

    print("\n\n[TEST 6] UnsupportedProtocolVersionError")
    response = client._send_request(
        "tools/list", protocol_version="1900-01-01")
    assert response.status_code == 400
    error = response.json().get("error", {})
    assert error.get("code") == - \
        32022, f"Expected -32022, got {error.get('code')}"
    print("✅ UnsupportedProtocolVersionError: PASSED")

    print("\n\n[TEST 7] HeaderMismatch (Mcp-Method != body method)")
    response = client._send_request(
        "tools/list", header_overrides={"Mcp-Method": "tools/call"})
    assert response.status_code == 400
    error = response.json().get("error", {})
    assert error.get("code") == - \
        32020, f"Expected -32020, got {error.get('code')}"
    print("✅ HeaderMismatch: PASSED")

    print("\n\n" + "=" * 60)
    print("All Tests PASSED! ✅")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="MCP Streamable HTTP Test Client")
    parser.add_argument(
        "server_url", help="MCP server base URL (e.g. http://localhost:11100)")
    parser.add_argument("--api-key", dest="api_key",
                        default=None, help="X-API-Key header value")
    args = parser.parse_args()

    client = MCPClient(args.server_url, api_key=args.api_key)

    try:
        run_test_suite(client)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
