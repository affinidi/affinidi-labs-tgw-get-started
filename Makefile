# ──────────────────────────────────────────────────────────────────────────────
#  affinidi-labs-tgw-get-started — root Makefile
#
#  Targets for the auth0-mcp-surface chat demo + its MCP server.
#    make local-up   → run BOTH: chat backend (:8642) + MCP server (:11000)
#    make serve      → chat backend only (honors backend/.env)
#    make mcp        → MCP server only (:11000)
#    make dev        → two-server hot reload (frontend :5137 + backend :8642)
# ──────────────────────────────────────────────────────────────────────────────

APP_DIR   := auth0-mcp-surface
PORT      ?= 8642
MCP_PORT  ?= 11000

.DEFAULT_GOAL := help

.PHONY: help local-up serve mcp dev local-down docker-up docker-down _preflight _build-frontend

help: ## Show available targets
	@echo ""
	@echo "  Agent Gateway chat surface — make targets"
	@echo ""
	@echo "  make local-up      Run BOTH chat backend (:$(PORT)) + MCP server (:$(MCP_PORT))"
	@echo "                     Each honors its own config; proxy them separately."
	@echo "  make serve         Chat backend only (honors backend/.env)"
	@echo "  make mcp           MCP server only — calculator + weather + chat (:$(MCP_PORT))"
	@echo "  make dev           Two-server hot-reload (frontend :5137 + backend :$(PORT))"
	@echo "  make local-down    Stop anything started above (frees :$(PORT), :5137, :$(MCP_PORT))"
	@echo "  make docker-up     Build + run the chat container (honors backend/.env)"
	@echo "  make docker-down   Stop the container"
	@echo ""

_preflight:
	@command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is required"; exit 1; }
	@command -v node    >/dev/null 2>&1 || { echo "ERROR: node is required"; exit 1; }

_build-frontend: _preflight
	@echo "→ Building frontend (single-origin: relative API base)…"
	cd $(APP_DIR)/frontend && npm install && PUBLIC_API_BASE="" npm run build

local-up: _build-frontend ## Run chat backend (:$(PORT)) + MCP server (:$(MCP_PORT))
	@echo "→ chat backend :$(PORT) (backend/.env) + MCP server :$(MCP_PORT)"
	@echo "  Ctrl-C stops both. Proxy each service separately for a public deploy."
	@bash -c 'trap "kill 0" EXIT INT TERM; \
	  ( cd $(APP_DIR)/backend && ([ -f .env ] || cp .env.example .env) && \
	    ([ -d .venv ] || python3 -m venv .venv) && \
	    .venv/bin/pip install --quiet -r requirements.txt && .venv/bin/python main.py ) & \
	  ( cd mcp && ./run.sh ) & \
	  wait'

serve: _build-frontend ## Chat backend only (honors backend/.env)
	@echo "→ Starting chat backend with backend/.env…"
	cd $(APP_DIR)/backend && \
	  ( [ -f .env ] || cp .env.example .env ) && \
	  ( [ -d .venv ] || python3 -m venv .venv ) && \
	  .venv/bin/pip install --quiet -r requirements.txt && \
	  .venv/bin/python main.py

mcp: _preflight ## MCP server only (calculator + weather + chat) on :$(MCP_PORT)
	@echo "→ MCP server on http://localhost:$(MCP_PORT)  (expose it, then register in the gateway)"
	cd mcp && ./run.sh

dev: _preflight ## Two-server hot-reload (frontend :5137 + backend :$(PORT))
	cd $(APP_DIR) && ./dev.sh

local-down: ## Stop local-up / serve / mcp / dev processes
	@lsof -ti:$(PORT)     2>/dev/null | xargs kill 2>/dev/null || true
	@lsof -ti:5137        2>/dev/null | xargs kill 2>/dev/null || true
	@lsof -ti:$(MCP_PORT) 2>/dev/null | xargs kill 2>/dev/null || true
	@pkill -f "astro dev" 2>/dev/null || true
	@echo "stopped (freed :$(PORT), :5137, :$(MCP_PORT))."

docker-up: ## Build + run the chat container (honors backend/.env)
	cd $(APP_DIR) && docker compose up --build

docker-down: ## Stop the container
	cd $(APP_DIR) && docker compose down
