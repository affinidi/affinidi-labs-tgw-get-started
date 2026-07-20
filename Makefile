# ──────────────────────────────────────────────────────────────────────────────
#  affinidi-labs-tgw-get-started — root Makefile
#
#  Targets for the auth0-mcp-surface chat demo + its chat MCP server.
#    make local-up   → run ALL: frontend (:5137) + chat backend (:8642) + chat MCP server (:9740)
#    make serve      → chat backend only (honors backend/.env)
#    make mcp        → chat MCP server only (:9740)
#    make dev        → two-server hot reload (frontend :5137 + backend :8642)
# ──────────────────────────────────────────────────────────────────────────────

APP_DIR   := auth0-mcp-surface
MCP_DIR   := auth0-mcp-surface/mcp-server
PORT      ?= 8642
MCP_PORT  ?= 9740

# AWS SSO profile for local development (Bedrock LLM access)
AWS_PROFILE_NAME ?= affinidi-genesis-lab-dev-sa-prototypes:Developer

.DEFAULT_GOAL := help

.PHONY: help chat-auth0-local-up chat-auth0-backend chat-auth0-mcp dev chat-auth0-local-down docker-up docker-down \
        _preflight _build-frontend _refresh-aws-creds _ensure-mcp-env

help: ## Show available targets
	@echo ""
	@echo "  Agent Gateway auth0 MCP chat surface — make targets"
	@echo ""
	@echo "  make chat-auth0-local-up   Run frontend (:5137) + backend (:$(PORT)) + MCP server (:$(MCP_PORT))"
	@echo "                             Auto-refreshes AWS SSO credentials for Bedrock LLM"
	@echo "  make chat-auth0-backend    Chat backend only (honors backend/.env)"
	@echo "  make chat-auth0-mcp        Chat MCP server only — the \`chat\` tool (:$(MCP_PORT))"
	@echo "                             Auto-refreshes AWS SSO credentials for Bedrock LLM"
	@echo "  make dev                   Two-server hot-reload (frontend :5137 + backend :$(PORT))"
	@echo "  make chat-auth0-local-down Stop all services (frees :$(PORT), :5137, :$(MCP_PORT))"
	@echo "  make docker-up             Build + run the chat container (honors backend/.env)"
	@echo "  make docker-down           Stop the container"
	@echo ""
	@echo "  AWS Setup:"
	@echo "    - AWS SSO profile: $(AWS_PROFILE_NAME)"
	@echo "    - Override: AWS_PROFILE_NAME=your-profile make chat-auth0-mcp"
	@echo "    - Alternative: Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN in mcp-server/.env"
	@echo ""

_preflight:
	@command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is required"; exit 1; }
	@command -v node    >/dev/null 2>&1 || { echo "ERROR: node is required"; exit 1; }

_build-frontend: _preflight
	@echo "→ Building frontend (single-origin: relative API base)…"
	cd $(APP_DIR)/frontend && npm install && PUBLIC_BACKEND_URL="" npm run build

_ensure-mcp-env:
	@if [ ! -f "$(MCP_DIR)/.env" ]; then \
		echo "→ Creating $(MCP_DIR)/.env from .env.example..."; \
		cp $(MCP_DIR)/.env.example $(MCP_DIR)/.env; \
	fi

_refresh-aws-creds: _ensure-mcp-env
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "🔐 Checking AWS credentials..."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@if aws sts get-caller-identity --profile "$(AWS_PROFILE_NAME)" > /dev/null 2>&1; then \
		echo "✓ AWS credentials still valid"; \
	else \
		echo "⚠ AWS credentials expired or missing, refreshing..."; \
		aws sso login --profile "$(AWS_PROFILE_NAME)" || true; \
	fi
	@echo "Exporting credentials to $(MCP_DIR)/.env..."
	@eval "$$(aws configure export-credentials --profile "$(AWS_PROFILE_NAME)" --format env)" && \
	if [ -n "$$AWS_ACCESS_KEY_ID" ]; then \
		grep -q '^AWS_ACCESS_KEY_ID=' $(MCP_DIR)/.env && \
		sed -i '' 's|^AWS_ACCESS_KEY_ID=.*|AWS_ACCESS_KEY_ID='"$$AWS_ACCESS_KEY_ID"'|' $(MCP_DIR)/.env || \
		echo "AWS_ACCESS_KEY_ID=$$AWS_ACCESS_KEY_ID" >> $(MCP_DIR)/.env; \
		grep -q '^AWS_SECRET_ACCESS_KEY=' $(MCP_DIR)/.env && \
		sed -i '' 's|^AWS_SECRET_ACCESS_KEY=.*|AWS_SECRET_ACCESS_KEY='"$$AWS_SECRET_ACCESS_KEY"'|' $(MCP_DIR)/.env || \
		echo "AWS_SECRET_ACCESS_KEY=$$AWS_SECRET_ACCESS_KEY" >> $(MCP_DIR)/.env; \
		grep -q '^AWS_SESSION_TOKEN=' $(MCP_DIR)/.env && \
		sed -i '' 's|^AWS_SESSION_TOKEN=.*|AWS_SESSION_TOKEN='"$$AWS_SESSION_TOKEN"'|' $(MCP_DIR)/.env || \
		echo "AWS_SESSION_TOKEN=$$AWS_SESSION_TOKEN" >> $(MCP_DIR)/.env; \
		echo "✓ AWS credentials exported to $(MCP_DIR)/.env"; \
	else \
		echo "⚠ Failed to export credentials — check AWS SSO profile"; \
		exit 1; \
	fi

chat-auth0-local-up: _refresh-aws-creds _build-frontend ## Run frontend (:5137) + chat backend (:$(PORT)) + chat MCP server (:$(MCP_PORT))
	@echo "→ frontend :5137 + chat backend :$(PORT) (backend/.env) + chat MCP server :$(MCP_PORT)"
	@echo "  Ctrl-C stops all three. Proxy each service separately for a public deploy."
	@bash -c 'trap "kill 0" EXIT INT TERM; \
	  ( cd $(APP_DIR)/backend && ([ -f .env ] || cp .env.example .env) && \
	    ([ -d .venv ] || python3 -m venv .venv) && \
	    .venv/bin/pip install --quiet -r requirements.txt && .venv/bin/python main.py ) & \
	  ( cd $(MCP_DIR) && ./run.sh ) & \
	  ( cd $(APP_DIR)/frontend && npm run dev ) & \
	  wait'

chat-auth0-backend: _build-frontend ## Chat backend only (honors backend/.env)
	@echo "→ Starting chat backend with backend/.env…"
	cd $(APP_DIR)/backend && \
	  ( [ -f .env ] || cp .env.example .env ) && \
	  ( [ -d .venv ] || python3 -m venv .venv ) && \
	  .venv/bin/pip install --quiet -r requirements.txt && \
	  .venv/bin/python main.py

chat-auth0-mcp: _refresh-aws-creds _preflight ## Chat MCP server only (the `chat` tool) on :$(MCP_PORT)
	@echo "→ Chat MCP server on http://localhost:$(MCP_PORT)  (expose it, then register in the gateway)"
	cd $(MCP_DIR) && ./run.sh

dev: _preflight ## Two-server hot-reload (frontend :5137 + backend :$(PORT))
	cd $(APP_DIR) && ./dev.sh

chat-auth0-local-down: ## Stop chat-auth0-local-up / chat-auth0-backend / chat-auth0-mcp / dev processes
	@lsof -ti:$(PORT)     2>/dev/null | xargs kill 2>/dev/null || true
	@lsof -ti:5137        2>/dev/null | xargs kill 2>/dev/null || true
	@lsof -ti:$(MCP_PORT) 2>/dev/null | xargs kill 2>/dev/null || true
	@pkill -f "astro dev" 2>/dev/null || true
	@echo "stopped (freed :$(PORT), :5137, :$(MCP_PORT))."

docker-up: ## Build + run the chat container (honors backend/.env)
	cd $(APP_DIR) && docker compose up --build

docker-down: ## Stop the container
	cd $(APP_DIR) && docker compose down
