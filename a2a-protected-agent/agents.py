#!/usr/bin/env python3
"""
Multi-Agent Server  –  entry point.

Mounts the Personal Agent and Finance Agent on a single Starlette/uvicorn
instance at port 10000:

  POST /a2a/personal-agent/   – Personal Agent JSON-RPC endpoint
  POST /a2a/finance-agent/    – Finance Agent JSON-RPC endpoint
  GET  /a2a/personal-agent/.well-known/agent.json
  GET  /a2a/finance-agent/.well-known/agent.json
  GET  /health

The Personal Agent detects finance-related keywords and delegates those
queries to the Finance Agent via the A2A client (agent-to-agent call).
"""

import personal_agent
import finance_agent
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.apps import A2AStarletteApplication
from starlette.routing import Mount, Route
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.requests import Request
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware import Middleware
from starlette.applications import Starlette
import uvicorn
import httpx
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the same directory as this file (if present)
load_dotenv(Path(__file__).parent / ".env")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 10000))
HOST = os.environ.get("HOST", "0.0.0.0")
BASE_URL = os.environ.get("BASE_URL", f"http://localhost:{PORT}")

PERSONAL_AGENT_URL = os.environ.get(
    "PERSONAL_AGENT_URL",    f"{BASE_URL}/a2a/personal-agent/")
FINANCE_AGENT_URL = os.environ.get(
    "FINANCE_AGENT_URL",     f"{BASE_URL}/a2a/finance-agent/")
PERSONAL_AGENT_TG_URL = os.environ.get("PERSONAL_AGENT_TG_URL", "")
FINANCE_AGENT_TG_URL = os.environ.get("FINANCE_AGENT_TG_URL",  "")


def build_app() -> Starlette:
    # ── Finance Agent ──────────────────────────────────────────────────────────
    finance_card = finance_agent.build_card(BASE_URL)
    finance_app = A2AStarletteApplication(
        agent_card=finance_card,
        http_handler=DefaultRequestHandler(
            agent_executor=finance_agent.FinanceAgentExecutor(),
            task_store=InMemoryTaskStore(),
        ),
    ).build()

    # ── Personal Agent ─────────────────────────────────────────────────────────
    # Tell the personal agent where the finance agent lives
    personal_agent._FINANCE_AGENT_URL = FINANCE_AGENT_URL

    personal_card = personal_agent.build_card(BASE_URL)
    personal_app = A2AStarletteApplication(
        agent_card=personal_card,
        http_handler=DefaultRequestHandler(
            agent_executor=personal_agent.PersonalAgentExecutor(),
            task_store=InMemoryTaskStore(),
        ),
    ).build()

    # ── Health ─────────────────────────────────────────────────────────────────
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({
            "status": "healthy",
            "agents": [
                {
                    "name": "Personal Assistant",
                    "endpoint": PERSONAL_AGENT_URL,
                    "agent_card": f"{PERSONAL_AGENT_URL.rstrip('/')}/.well-known/agent.json",
                    "note": "Routes finance queries to Finance Agent via A2A client",
                },
                {
                    "name": "Finance Agent",
                    "endpoint": FINANCE_AGENT_URL,
                    "agent_card": f"{FINANCE_AGENT_URL.rstrip('/')}/.well-known/agent.json",
                },
            ],
        })

    # ── Config (consumed by chat_app.html) ────────────────────────────────────
    async def config(request: Request) -> JSONResponse:
        return JSONResponse({
            "personalUrl":   PERSONAL_AGENT_URL,
            "financeUrl":    FINANCE_AGENT_URL,
            "personalTgUrl": PERSONAL_AGENT_TG_URL,
            "financeTgUrl":  FINANCE_AGENT_TG_URL,
        })

    # ── Generic CORS proxy (forwards GET/POST to external URLs) ──────────────
    async def proxy(request: Request) -> Response:
        target = request.query_params.get("url", "").strip()
        if not target:
            return JSONResponse({"error": "missing url param"}, status_code=400)
        try:
            body = await request.body()
            headers = {"Accept": "application/json"}
            if body:
                headers["Content-Type"] = "application/json"
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.request(
                    method=request.method,
                    url=target,
                    content=body or None,
                    headers=headers,
                )
            return Response(
                content=r.content,
                status_code=r.status_code,
                media_type="application/json",
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=502)

    # ── Chat UI ────────────────────────────────────────────────────────────────
    _chat_html = Path(__file__).parent / "chat_app.html"

    async def chat_ui(request: Request) -> HTMLResponse:
        return HTMLResponse(_chat_html.read_text(encoding="utf-8"))

    return Starlette(
        routes=[
            Route("/health",  health,  methods=["GET"]),
            Route("/config",  config,  methods=["GET"]),
            Route("/proxy",   proxy,   methods=["GET", "POST"]),
            Route("/",        chat_ui, methods=["GET", "HEAD"]),
            Mount("/a2a/personal-agent", app=personal_app),
            Mount("/a2a/finance-agent",  app=finance_app),
        ],
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )
        ],
    )


def main() -> None:
    logger.info("=" * 60)
    logger.info("Multi-Agent Server  (a2a-sdk v0.3.x)")
    logger.info("Port: %d", PORT)
    logger.info("Endpoints:")
    logger.info("  Personal Assistant -> %s/a2a/personal-agent/", BASE_URL)
    logger.info("  Finance Agent      -> %s/a2a/finance-agent/",  BASE_URL)
    logger.info("Agent Cards:")
    logger.info("  %s/a2a/personal-agent/.well-known/agent.json", BASE_URL)
    logger.info("  %s/a2a/finance-agent/.well-known/agent.json",  BASE_URL)
    logger.info("Health: %s/health", BASE_URL)
    logger.info("Chat UI: %s/", BASE_URL)
    logger.info(
        "Agent-to-Agent: Personal Agent routes finance queries via A2A client")
    logger.info("=" * 60)

    _print_url_banner()
    uvicorn.run(build_app(), host=HOST, port=PORT)


def _print_url_banner() -> None:
    print("\n" + "=" * 60, flush=True)
    print("  App is running!", flush=True)
    print(f"  URL:               {BASE_URL}/", flush=True)
    print(f"  Personal Agent:    {BASE_URL}/a2a/personal-agent/", flush=True)
    print(f"  Finance Agent:     {BASE_URL}/a2a/finance-agent/", flush=True)
    print(f"  Health:            {BASE_URL}/health", flush=True)
    print("=" * 60 + "\n", flush=True)


if __name__ == "__main__":
    main()
