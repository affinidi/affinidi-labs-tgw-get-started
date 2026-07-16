#!/usr/bin/env python3
"""
Chat MCP Server (auth0-mcp-surface)

A minimal Model Context Protocol server exposing a single `chat` tool. It is the
upstream the chat surface talks to (via the Trust Gateway). It answers using AWS
Bedrock when configured, otherwise returns a friendly stub — so getting-started
works with no LLM.

Protocol: JSON-RPC 2.0 over `POST /` (initialize, tools/list, tools/call), plus
`GET /` and `GET /health` for health checks — matching the tutorial mcp/ server
so the gateway proxies it identically.

Run:  python mcp_server.py   (default port 9740)
Env (optional, see .env.example):
  BEDROCK_MODEL_ID   Bedrock model id — set to enable real answers (else stub)
  AWS_REGION         default us-east-1
  PORT               default 9740
"""

import os
import json
from typing import Any, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PORT = int(os.environ.get("PORT", 9740))

SERVER_INFO = {"name": "Chat MCP Server", "version": "1.0.0"}
SERVER_CAPABILITIES = {"tools": {"listChanged": True}}

TOOLS = [
    {
        "name": "chat",
        "description": "Chat with an assistant. Answers via AWS Bedrock when configured, otherwise returns a stub response.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The user's message to the assistant"
                }
            },
            "required": ["message"]
        }
    }
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    model_id = os.environ.get("BEDROCK_MODEL_ID")
    print(f"\n{'='*60}")
    print(f"🚀 {SERVER_INFO['name']} v{SERVER_INFO['version']} on :{PORT}")
    print(f"   Tools: {', '.join(t['name'] for t in TOOLS)}")
    print(f"   Bedrock: {'enabled (' + model_id + ')' if model_id else 'stub mode (BEDROCK_MODEL_ID not set)'}")
    print(f"{'='*60}\n")
    yield
    print("\n👋 Server shutting down\n")


app = FastAPI(title="Chat MCP Server", lifespan=lifespan)


def create_json_rpc_response(id: Any, result: Any) -> Dict:
    return {
        "jsonrpc": "2.0",
        "id": id,
        "result": result,
        "_meta": {"agentIdentity": {"name": SERVER_INFO["name"]}},
    }


def create_json_rpc_error(id: Any, code: int, message: str, data: Any = None) -> Dict:
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": id, "error": error}


@app.get("/health")
@app.get("/")
async def health_check():
    return {"status": "healthy", "server": SERVER_INFO}


@app.post("/")
async def mcp_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(create_json_rpc_error(None, -32700, "Parse error", str(e)), status_code=200)

    if body.get("jsonrpc") != "2.0":
        return JSONResponse(create_json_rpc_error(body.get("id"), -32600, "Invalid Request"), status_code=200)

    method = body.get("method")
    params = body.get("params", {})
    request_id = body.get("id")
    print(f"📨 method={method} id={request_id}")

    if method == "initialize":
        return handle_initialize(request_id, params)
    elif method == "tools/list":
        return handle_tools_list(request_id, params)
    elif method == "tools/call":
        return handle_tools_call(request_id, params)
    else:
        return JSONResponse(create_json_rpc_error(request_id, -32601, f"Method not found: {method}"), status_code=200)


def handle_initialize(request_id: Any, params: Dict) -> JSONResponse:
    result = {
        "protocolVersion": "2024-11-05",
        "capabilities": SERVER_CAPABILITIES,
        "serverInfo": SERVER_INFO,
    }
    return JSONResponse(create_json_rpc_response(request_id, result))


def handle_tools_list(request_id: Any, params: Dict) -> JSONResponse:
    return JSONResponse(create_json_rpc_response(request_id, {"tools": TOOLS}))


def handle_tools_call(request_id: Any, params: Dict) -> JSONResponse:
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    print(f"🔧 tool={tool_name} args={arguments}")

    if tool_name == "chat":
        return execute_chat(request_id, arguments)
    return JSONResponse(create_json_rpc_error(request_id, -32602, f"Unknown tool: {tool_name}"), status_code=200)


def execute_chat(request_id: Any, arguments: Dict) -> JSONResponse:
    """Answer via AWS Bedrock when configured; otherwise return a stub."""
    message = (arguments.get("message") or "").strip()
    if not message:
        return JSONResponse(create_json_rpc_error(request_id, -32602, "message is required"), status_code=200)

    model_id = os.environ.get("BEDROCK_MODEL_ID")

    if not model_id:
        text = (
            "🛈 Chat is running in stub mode — no LLM is configured.\n\n"
            "To get real answers, set BEDROCK_MODEL_ID (and AWS credentials) on "
            "this MCP server (see .env.example).\n\n"
            f"You said: {message}"
        )
        return JSONResponse(create_json_rpc_response(request_id, {"content": [{"type": "text", "text": text}]}))

    # Real answer via AWS Bedrock Converse API.
    try:
        import boto3  # lazy import — only needed when Bedrock is configured

        client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        response = client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": message}]}],
        )
        text = response["output"]["message"]["content"][0]["text"]
    except Exception as e:  # noqa: BLE001 — surface any Bedrock error as text
        text = f"(Bedrock error: {e})"

    return JSONResponse(create_json_rpc_response(request_id, {"content": [{"type": "text", "text": text}]}))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
