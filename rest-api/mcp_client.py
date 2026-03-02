#!/usr/bin/env python3
"""
MCP Test Client

A simple client to test the MCP server by calling its tools.
"""

import requests
import json
import sys
from typing import Any, Dict, Optional


class MCPClient:
    """Simple MCP client for testing"""

    def __init__(self, base_url: str = "http://localhost:12000", agent_identity: Optional[Dict] = None):
        self.base_url = base_url
        self.request_id = 0
        self.initialized = False
        self.agent_identity = agent_identity

    def _get_next_id(self) -> int:
        """Generate next request ID"""
        self.request_id += 1
        return self.request_id

    def _send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Send a JSON-RPC request to the server"""
        request_id = self._get_next_id()

        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "_meta": {
                "agentIdentity": self.agent_identity
            }
        }

        if params:
            payload["params"] = params

        print(f"\n{'='*60}")
        print(f"Request: {method} (id={request_id})")
        print(f"{'='*60}")
        print(json.dumps(payload, indent=2))

        try:
            response = requests.post(
                self.base_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            # Check status and print response body on error
            if response.status_code != 200:
                print(f"\n❌ HTTP {response.status_code} Error")
                print(f"Response body:")
                try:
                    error_data = response.json()
                    print(json.dumps(error_data, indent=2))
                except:
                    print(response.text)
                response.raise_for_status()

            result = response.json()

            print(f"\n{'='*60}")
            print(f"Response: {method} (id={request_id})")
            print(f"{'='*60}")
            print(json.dumps(result, indent=2))

            return result

        except requests.exceptions.RequestException as e:
            print(f"\n❌ Request failed: {e}")
            sys.exit(1)

    def initialize(self) -> Dict:
        """Initialize MCP connection"""
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": self.agent_identity
        }
        result = self._send_request("initialize", params)
        if result.get("result"):
            self.initialized = True
        return result

    def list_tools(self) -> Dict:
        """List available tools"""
        return self._send_request("tools/list")

    def call_tool(self, name: str, arguments: Dict) -> Dict:
        """Call a tool"""
        params = {
            "name": name,
            "arguments": arguments
        }
        return self._send_request("tools/call", params)


def run_test_suite(client: MCPClient):
    """Run complete test suite"""
    print("\n" + "="*60)
    print("MCP Test Suite")
    print("="*60)

    # Test 1: Initialize
    print("\n\n[TEST 1] Initialize Connection")
    result = client.initialize()
    assert result.get("result"), "Initialize failed"
    assert result["result"].get("protocolVersion") == "2024-11-05"
    print("✅ Initialize: PASSED")

    # Test 2: List Tools
    print("\n\n[TEST 2] List Tools")
    result = client.list_tools()
    assert result.get("result"), "List tools failed"
    tools = result["result"].get("tools", [])
    assert len(tools) == 2, f"Expected 2 tools, got {len(tools)}"
    print(f"✅ List Tools: PASSED ({len(tools)} tools)")

    # Test 3: Calculator - Addition
    print("\n\n[TEST 3] Calculator: Addition")
    result = client.call_tool(
        "calculator", {"operation": "add", "a": 15, "b": 27})
    assert result.get("result"), "Call tool failed"
    content = result["result"]["content"][0]["text"]
    assert "42" in content, f"Expected 42 in result, got: {content}"
    print("✅ Calculator Addition: PASSED")

    # Test 4: Calculator - Subtraction
    print("\n\n[TEST 4] Calculator: Subtraction")
    result = client.call_tool(
        "calculator", {"operation": "subtract", "a": 100, "b": 45})
    assert result.get("result"), "Call tool failed"
    content = result["result"]["content"][0]["text"]
    assert "55" in content, f"Expected 55 in result, got: {content}"
    print("✅ Calculator Subtraction: PASSED")

    # Test 5: Calculator - Multiplication
    print("\n\n[TEST 5] Calculator: Multiplication")
    result = client.call_tool(
        "calculator", {"operation": "multiply", "a": 12, "b": 8})
    assert result.get("result"), "Call tool failed"
    content = result["result"]["content"][0]["text"]
    assert "96" in content, f"Expected 96 in result, got: {content}"
    print("✅ Calculator Multiplication: PASSED")

    # Test 6: Calculator - Division
    print("\n\n[TEST 6] Calculator: Division")
    result = client.call_tool(
        "calculator", {"operation": "divide", "a": 144, "b": 12})
    assert result.get("result"), "Call tool failed"
    content = result["result"]["content"][0]["text"]
    assert "12" in content, f"Expected 12 in result, got: {content}"
    print("✅ Calculator Division: PASSED")

    # Test 7: Weather - Single day
    print("\n\n[TEST 7] Weather Forecast: Single Day")
    result = client.call_tool(
        "weather_forecast", {"city": "San Francisco", "days": 1})
    assert result.get("result"), "Call tool failed"
    content = result["result"]["content"][0]["text"]
    assert "San Francisco" in content, f"Expected city name in forecast"
    print("✅ Weather Single Day: PASSED")

    # Test 8: Weather - Multiple days
    print("\n\n[TEST 8] Weather Forecast: Multiple Days")
    result = client.call_tool(
        "weather_forecast", {"city": "New York", "days": 3})
    assert result.get("result"), "Call tool failed"
    content = result["result"]["content"][0]["text"]
    assert "New York" in content and "Day 2" in content, f"Expected 3-day forecast"
    print("✅ Weather Multiple Days: PASSED")

    print("\n\n" + "="*60)
    print("All Tests PASSED! ✅")
    print("="*60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python mcp_client.py <server_url>")
        print("Example: python mcp_client.py http://localhost:12000")
        sys.exit(1)

    server_url = sys.argv[1]

    # Create agent identity
    agent_identity = {
        "name": "MCP Test Client",
        "version": "1.0.0"
    }

    client = MCPClient(server_url,
                       agent_identity=agent_identity)

    try:
        run_test_suite(client)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
