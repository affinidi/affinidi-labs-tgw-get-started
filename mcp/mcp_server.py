#!/usr/bin/env python3
"""
Simple MCP Server

A basic Model Context Protocol server with calculator and weather tools.
"""

import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from typing import Any, Dict
from contextlib import asynccontextmanager

# Server info
SERVER_INFO = {
    "name": "Simple MCP Server",
    "version": "1.0.0"
}

SERVER_CAPABILITIES = {
    "tools": {
        "listChanged": True
    }
}

# Define tools
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
                "a": {
                    "type": "number",
                    "description": "First number"
                },
                "b": {
                    "type": "number",
                    "description": "Second number"
                }
            },
            "required": ["operation", "a", "b"]
        }
    },
    {
        "name": "weather_forecast",
        "description": "Get a weather forecast for a specified city",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name"
                },
                "days": {
                    "type": "number",
                    "description": "Number of days to forecast (1-7)",
                    "minimum": 1,
                    "maximum": 7
                }
            },
            "required": ["city"]
        }
    }
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"\n{'='*60}")
    print(f"🚀 {SERVER_INFO['name']} v{SERVER_INFO['version']}")
    print(f"   Available tools: {len(TOOLS)}")
    for tool in TOOLS:
        print(f"   - {tool['name']}: {tool['description']}")
    print(f"{'='*60}\n")
    yield
    # Shutdown
    print(f"\n👋 Server shutting down\n")

app = FastAPI(title="Simple MCP Server", lifespan=lifespan)


def create_json_rpc_response(id: Any, result: Any) -> Dict:
    """Create a JSON-RPC 2.0 success response"""
    msg = {
        "jsonrpc": "2.0",
        "id": id,
        "result": result,
        "_meta": {
            "agentIdentity": {
                "name": "Simple MCP Server",
            }
        }
    }
    print('Sending response: result=' + json.dumps(msg, indent=2))

    return msg


def create_json_rpc_error(id: Any, code: int, message: str, data: Any = None) -> Dict:
    """Create a JSON-RPC 2.0 error response"""
    error = {
        "code": code,
        "message": message
    }
    if data is not None:
        error["data"] = data

    return {
        "jsonrpc": "2.0",
        "id": id,
        "error": error
    }


@app.get("/health")
@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "server": SERVER_INFO}


@app.post("/")
async def mcp_endpoint(request: Request):
    """Main MCP JSON-RPC endpoint"""
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(
            create_json_rpc_error(None, -32700, "Parse error", str(e)),
            status_code=200
        )

    # Validate JSON-RPC
    if body.get("jsonrpc") != "2.0":
        return JSONResponse(
            create_json_rpc_error(body.get("id"), -32600, "Invalid Request"),
            status_code=200
        )

    method = body.get("method")
    params = body.get("params", {})
    request_id = body.get("id")

    print(f"📨 Received request: method={method}, id={request_id}")
    print(json.dumps(body, indent=2))

    # Route to appropriate handler
    if method == "initialize":
        return handle_initialize(request_id, params)
    elif method == "tools/list":
        return handle_tools_list(request_id, params)
    elif method == "tools/call":
        return handle_tools_call(request_id, params)
    else:
        return JSONResponse(
            create_json_rpc_error(request_id, -32601,
                                  f"Method not found: {method}"),
            status_code=200
        )


def handle_initialize(request_id: Any, params: Dict) -> JSONResponse:
    """Handle initialize request"""
    client_info = params.get("clientInfo", {})

    print(f"🤝 Initialize from client: {client_info.get('name', 'unknown')}")

    result = {
        "protocolVersion": "2024-11-05",
        "capabilities": SERVER_CAPABILITIES,
        "serverInfo": SERVER_INFO
    }

    return JSONResponse(create_json_rpc_response(request_id, result))


def handle_tools_list(request_id: Any, params: Dict) -> JSONResponse:
    """Handle tools/list request"""
    print("📋 Listing tools")

    result = {
        "tools": TOOLS
    }

    return JSONResponse(create_json_rpc_response(request_id, result))


def handle_tools_call(request_id: Any, params: Dict) -> JSONResponse:
    """Handle tools/call request"""
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    print(f"🔧 Calling tool: {tool_name} with args: {arguments}")

    # Execute tool
    if tool_name == "calculator":
        return execute_calculator(request_id, arguments)
    elif tool_name == "weather_forecast":
        return execute_weather_forecast(request_id, arguments)
    else:
        return JSONResponse(
            create_json_rpc_error(request_id, -32602,
                                  f"Unknown tool: {tool_name}"),
            status_code=200
        )


def execute_calculator(request_id: Any, arguments: Dict) -> JSONResponse:
    """Execute calculator tool"""
    operation = arguments.get("operation")
    a = arguments.get("a")
    b = arguments.get("b")

    # Validate inputs
    if operation not in ["add", "subtract", "multiply", "divide"]:
        return JSONResponse(
            create_json_rpc_error(
                request_id,
                -32602,
                f"Invalid operation: {operation}. Must be one of: add, subtract, multiply, divide"
            ),
            status_code=200
        )

    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return JSONResponse(
            create_json_rpc_error(request_id, -32602,
                                  "Both 'a' and 'b' must be numbers"),
            status_code=200
        )

    # Perform calculation
    try:
        if operation == "add":
            answer = a + b
            expr = f"{a} + {b}"
        elif operation == "subtract":
            answer = a - b
            expr = f"{a} - {b}"
        elif operation == "multiply":
            answer = a * b
            expr = f"{a} × {b}"
        elif operation == "divide":
            if b == 0:
                return JSONResponse(
                    create_json_rpc_error(
                        request_id, -32602, "Cannot divide by zero"),
                    status_code=200
                )
            answer = a / b
            expr = f"{a} ÷ {b}"

        result = {
            "content": [
                {
                    "type": "text",
                    "text": f"Calculation: {expr} = {answer}"
                }
            ]
        }

        return JSONResponse(create_json_rpc_response(request_id, result))

    except Exception as e:
        return JSONResponse(
            create_json_rpc_error(request_id, -32603,
                                  "Calculation error", str(e)),
            status_code=200
        )


def execute_weather_forecast(request_id: Any, arguments: Dict) -> JSONResponse:
    """Execute weather forecast tool"""
    city = arguments.get("city")
    days = arguments.get("days", 1)

    # Validate inputs
    if not city:
        return JSONResponse(
            create_json_rpc_error(request_id, -32602, "City is required"),
            status_code=200
        )

    if not isinstance(days, (int, float)) or days < 1 or days > 7:
        return JSONResponse(
            create_json_rpc_error(request_id, -32602,
                                  "Days must be a number between 1 and 7"),
            status_code=200
        )

    # Generate mock weather forecast
    import random

    conditions = ["Sunny", "Partly Cloudy",
                  "Cloudy", "Rainy", "Stormy", "Snowy"]

    forecast_text = f"Weather Forecast for {city}:\n\n"

    for day in range(1, int(days) + 1):
        condition = random.choice(conditions)
        temp_f = random.randint(45, 85)
        temp_c = round((temp_f - 32) * 5/9, 1)
        humidity = random.randint(30, 90)
        wind = random.randint(5, 25)

        day_label = "Today" if day == 1 else f"Day {day}"
        forecast_text += f"{day_label}: {condition}\n"
        forecast_text += f"  Temperature: {temp_f}°F ({temp_c}°C)\n"
        forecast_text += f"  Humidity: {humidity}%\n"
        forecast_text += f"  Wind: {wind} mph\n\n"

    result = {
        "content": [
            {
                "type": "text",
                "text": forecast_text.strip()
            }
        ]
    }

    return JSONResponse(create_json_rpc_response(request_id, result))


if __name__ == "__main__":
    print("=" * 60)
    print("Simple MCP Server")
    print("=" * 60)
    print(f"Server: {SERVER_INFO['name']} v{SERVER_INFO['version']}")
    print(f"Protocol: MCP 2024-11-05")
    print(f"Tools: {len(TOOLS)}")
    for tool in TOOLS:
        print(f"  • {tool['name']}")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=11000, log_level="info")
