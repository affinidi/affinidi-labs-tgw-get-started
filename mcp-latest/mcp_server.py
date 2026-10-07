#!/usr/bin/env python3
"""
MCP Server (Streamable HTTP transport, protocol version 2026-07-28)

Implements the latest MCP spec transport supported by the Agent Gateway.
Revision 2026-07-28 removed the `initialize` handshake and protocol-level
sessions entirely. Instead:
- Every request declares its protocol version per-request via
  `params._meta["io.modelcontextprotocol/protocolVersion"]`, mirrored in the
  `MCP-Protocol-Version` HTTP header.
- Every request also mirrors `method` into `Mcp-Method`, and `params.name`
  (for tools/call, resources/read, prompts/get) into `Mcp-Name`.
- Servers MUST implement `server/discover` so clients can learn supported
  versions/capabilities without a handshake.
- Structured tool output (`structuredContent`) is returned alongside
  classic `content`.
"""

import json
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

# ── Protocol constants ──────────────────────────────────────────────────────
LATEST_PROTOCOL_VERSION = "2026-07-28"
SUPPORTED_PROTOCOL_VERSIONS = {"2026-07-28"}

META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CLIENT_INFO = "io.modelcontextprotocol/clientInfo"
META_CLIENT_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"

SERVER_INFO = {
    "name": "Streamable HTTP MCP Server",
    "version": "3.0.0"
}

SERVER_CAPABILITIES = {
    "tools": {}
}

# Allow-list of origins permitted to call this server directly.
# When fronted by the Agent Gateway / ngrok, add those hosts here as needed.
ALLOWED_ORIGINS = {"*"}

TOOLS = [
    {
        "name": "calculator",
        "description": "Perform basic arithmetic calculations (addition, subtraction, multiplication, division)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "The operation to perform: add, subtract, multiply, divide",
                    "enum": ["add", "subtract", "multiply", "divide"]
                },
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"}
            },
            "required": ["operation", "a", "b"]
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "operation": {"type": "string"},
                "a": {"type": "number"},
                "b": {"type": "number"},
                "result": {"type": "number"}
            },
            "required": ["operation", "a", "b", "result"]
        }
    },
    {
        "name": "weather_forecast",
        "description": "Get a weather forecast for a specified city",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "days": {
                    "type": "number",
                    "description": "Number of days to forecast (1-7)",
                    "minimum": 1,
                    "maximum": 7
                }
            },
            "required": ["city"]
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "forecast": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "day": {"type": "number"},
                            "condition": {"type": "string"},
                            "temperature_f": {"type": "number"},
                            "temperature_c": {"type": "number"},
                            "humidity": {"type": "number"},
                            "wind_mph": {"type": "number"}
                        }
                    }
                }
            },
            "required": ["city", "forecast"]
        }
    }
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"\n{'='*60}")
    print(f"🚀 {SERVER_INFO['name']} v{SERVER_INFO['version']}")
    print(f"   Transport: Streamable HTTP (stateless, no sessions)")
    print(
        f"   Protocol:  {LATEST_PROTOCOL_VERSION} (per-request, no initialize handshake)")
    print(f"   Available tools: {len(TOOLS)}")
    for tool in TOOLS:
        print(f"   - {tool['name']}: {tool['description']}")
    print(f"{'='*60}\n")
    yield
    print("\n👋 Server shutting down\n")


app = FastAPI(title=SERVER_INFO["name"], lifespan=lifespan)


# ── JSON-RPC helpers ─────────────────────────────────────────────────────────
def rpc_result(id: Any, result: Any) -> Dict:
    if isinstance(result, dict):
        result.setdefault("resultType", "complete")
    return {"jsonrpc": "2.0", "id": id, "result": result}


def rpc_error(id: Any, code: int, message: str, data: Any = None) -> Dict:
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": id, "error": error}


def unsupported_version_error(id: Any, requested: Optional[str]) -> Dict:
    return rpc_error(
        id, -32022, "Unsupported protocol version",
        {"supported": sorted(SUPPORTED_PROTOCOL_VERSIONS),
         "requested": requested}
    )


def header_mismatch_error(id: Any, message: str) -> Dict:
    return rpc_error(id, -32020, f"Header mismatch: {message}")


@app.get("/health")
@app.get("/")
async def health_check():
    return {"status": "healthy", "server": SERVER_INFO, "protocolVersion": LATEST_PROTOCOL_VERSION}


def check_origin(request: Request) -> Optional[JSONResponse]:
    """Basic DNS-rebinding mitigation per the Streamable HTTP security guidance."""
    if "*" in ALLOWED_ORIGINS:
        return None
    origin = request.headers.get("origin")
    if origin is not None and origin not in ALLOWED_ORIGINS:
        return JSONResponse(rpc_error(None, -32600, f"Forbidden origin: {origin}"), status_code=403)
    return None


def validate_request_metadata(request: Request, body: Dict) -> Optional[JSONResponse]:
    """
    Validate the modern (2026-07-28) per-request metadata headers:
    MCP-Protocol-Version, Mcp-Method, and (when applicable) Mcp-Name — each
    MUST match the corresponding value in the request body.
    """
    request_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {}) or {}
    meta = params.get("_meta", {}) or {}

    header_version = request.headers.get("mcp-protocol-version")
    body_version = meta.get(META_PROTOCOL_VERSION)

    if not header_version or not body_version:
        return JSONResponse(
            header_mismatch_error(
                request_id, "MCP-Protocol-Version header or body _meta field is missing"),
            status_code=400
        )
    if header_version != body_version:
        return JSONResponse(
            header_mismatch_error(
                request_id,
                f"MCP-Protocol-Version header '{header_version}' does not match body value '{body_version}'"
            ),
            status_code=400
        )
    if body_version not in SUPPORTED_PROTOCOL_VERSIONS:
        return JSONResponse(unsupported_version_error(request_id, body_version), status_code=400)

    header_method = request.headers.get("mcp-method")
    if not header_method or header_method != method:
        return JSONResponse(
            header_mismatch_error(
                request_id, f"Mcp-Method header does not match body method '{method}'"),
            status_code=400
        )

    if method in ("tools/call", "resources/read", "prompts/get"):
        body_name = params.get("name") or params.get("uri")
        header_name = request.headers.get("mcp-name")
        if not header_name or header_name != body_name:
            return JSONResponse(
                header_mismatch_error(
                    request_id, f"Mcp-Name header does not match body value '{body_name}'"),
                status_code=400
            )

    return None


@app.post("/mcp")
async def mcp_post(request: Request):
    """Stateless Streamable HTTP endpoint — no sessions, no initialize handshake."""
    origin_error = check_origin(request)
    if origin_error:
        return origin_error

    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(rpc_error(None, -32700, "Parse error", str(e)), status_code=400)

    # JSON-RPC batching is not part of this revision's Streamable HTTP transport.
    if isinstance(body, list):
        return JSONResponse(
            rpc_error(None, -32600, "JSON-RPC batching is not supported"),
            status_code=400
        )

    if body.get("jsonrpc") != "2.0":
        return JSONResponse(rpc_error(body.get("id"), -32600, "Invalid Request"), status_code=400)

    method = body.get("method")
    params = body.get("params", {}) or {}
    request_id = body.get("id")

    print(f"📨 method={method} id={request_id}")
    print(json.dumps(body, indent=2))

    validation_error = validate_request_metadata(request, body)
    if validation_error:
        return validation_error

    if method == "server/discover":
        return JSONResponse(handle_discover(request_id, params))
    elif method == "tools/list":
        return JSONResponse(handle_tools_list(request_id))
    elif method == "tools/call":
        return JSONResponse(handle_tools_call(request_id, params))
    else:
        # Unknown/legacy methods (e.g. `initialize`) are rejected per spec:
        # modern servers have no handshake, so legacy clients fail here.
        return JSONResponse(
            rpc_error(request_id, -32601, f"Method not found: {method}"),
            status_code=404
        )


@app.get("/mcp")
async def mcp_get():
    """Revision 2026-07-28 removed the GET stream endpoint — POST only."""
    return Response(status_code=405, headers={"Allow": "POST"})


@app.delete("/mcp")
async def mcp_delete():
    """Revision 2026-07-28 removed protocol-level sessions — nothing to terminate."""
    return Response(status_code=405, headers={"Allow": "POST"})


def handle_discover(request_id: Any, params: Dict) -> Dict:
    meta = params.get("_meta", {}) or {}
    client_info = meta.get(META_CLIENT_INFO, {})
    print(
        f"🔎 server/discover from client: {client_info.get('name', 'unknown')}")

    result = {
        "resultType": "complete",
        "supportedVersions": sorted(SUPPORTED_PROTOCOL_VERSIONS),
        "capabilities": SERVER_CAPABILITIES,
        "_meta": {META_SERVER_INFO: SERVER_INFO},
        "instructions": "This server provides a calculator and a weather forecast tool.",
        "ttlMs": 3600000,
        "cacheScope": "public"
    }
    return rpc_result(request_id, result)


def handle_tools_list(request_id: Any) -> Dict:
    print("📋 Listing tools")
    return rpc_result(request_id, {
        "tools": TOOLS,
        "ttlMs": 300000,
        "cacheScope": "public"
    })


def handle_tools_call(request_id: Any, params: Dict) -> Dict:
    tool_name = params.get("name")
    arguments = params.get("arguments", {}) or {}

    print(f"🔧 Calling tool: {tool_name} with args: {arguments}")

    if tool_name == "calculator":
        return execute_calculator(request_id, arguments)
    elif tool_name == "weather_forecast":
        return execute_weather_forecast(request_id, arguments)
    else:
        return rpc_error(request_id, -32602, f"Unknown tool: {tool_name}")


def execute_calculator(request_id: Any, arguments: Dict) -> Dict:
    operation = arguments.get("operation")
    a = arguments.get("a")
    b = arguments.get("b")

    if operation not in ["add", "subtract", "multiply", "divide"]:
        return rpc_error(request_id, -32602, f"Invalid operation: {operation}")

    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return rpc_error(request_id, -32602, "Both 'a' and 'b' must be numbers")

    if operation == "add":
        answer = a + b
        expr = f"{a} + {b}"
    elif operation == "subtract":
        answer = a - b
        expr = f"{a} - {b}"
    elif operation == "multiply":
        answer = a * b
        expr = f"{a} × {b}"
    else:  # divide
        if b == 0:
            return rpc_error(request_id, -32602, "Cannot divide by zero")
        answer = a / b
        expr = f"{a} ÷ {b}"

    structured = {"operation": operation, "a": a, "b": b, "result": answer}
    result = {
        "content": [{"type": "text", "text": f"Calculation: {expr} = {answer}"}],
        "structuredContent": structured
    }
    return rpc_result(request_id, result)


def execute_weather_forecast(request_id: Any, arguments: Dict) -> Dict:
    import random

    city = arguments.get("city")
    days = arguments.get("days", 1)

    if not city:
        return rpc_error(request_id, -32602, "City is required")

    if not isinstance(days, (int, float)) or days < 1 or days > 7:
        return rpc_error(request_id, -32602, "Days must be a number between 1 and 7")

    conditions = ["Sunny", "Partly Cloudy",
                  "Cloudy", "Rainy", "Stormy", "Snowy"]

    forecast_text = f"Weather Forecast for {city}:\n\n"
    structured_days = []

    for day in range(1, int(days) + 1):
        condition = random.choice(conditions)
        temp_f = random.randint(45, 85)
        temp_c = round((temp_f - 32) * 5 / 9, 1)
        humidity = random.randint(30, 90)
        wind = random.randint(5, 25)

        day_label = "Today" if day == 1 else f"Day {day}"
        forecast_text += f"{day_label}: {condition}\n"
        forecast_text += f"  Temperature: {temp_f}°F ({temp_c}°C)\n"
        forecast_text += f"  Humidity: {humidity}%\n"
        forecast_text += f"  Wind: {wind} mph\n\n"

        structured_days.append({
            "day": day,
            "condition": condition,
            "temperature_f": temp_f,
            "temperature_c": temp_c,
            "humidity": humidity,
            "wind_mph": wind
        })

    result = {
        "content": [{"type": "text", "text": forecast_text.strip()}],
        "structuredContent": {"city": city, "forecast": structured_days}
    }
    return rpc_result(request_id, result)


if __name__ == "__main__":
    print("=" * 60)
    print(SERVER_INFO["name"])
    print("=" * 60)
    print(f"Transport: Streamable HTTP (POST only, /mcp — no sessions)")
    print(f"Protocol:  {LATEST_PROTOCOL_VERSION}")
    print(f"Tools: {len(TOOLS)}")
    for tool in TOOLS:
        print(f"  • {tool['name']}")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=11100, log_level="info")
