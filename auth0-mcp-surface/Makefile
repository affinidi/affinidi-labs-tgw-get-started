# ──────────────────────────────────────────────────────────────────────────────
#  auth0-mcp-surface — OAuth Caller Context + Credential Delegation Demo
#
#  A browser-based chat interface demonstrating:
#    - Google OAuth (caller context)
#    - Agent Gateway verification
#    - Auth0 credential delegation
#    - Automatic popup-based consent flow
# ──────────────────────────────────────────────────────────────────────────────

PORT      ?= 8642
MCP_PORT  ?= 9740

# AWS SSO profile for local development (Bedrock LLM access)
# Leave empty to run MCP server in stub mode (no Bedrock)
AWS_PROFILE_NAME ?=

.DEFAULT_GOAL := help

.PHONY: help local-up backend mcp dev local-down docker-up docker-down \
        _preflight _build-frontend _refresh-aws-creds _ensure-mcp-env

help: ## Show available targets
	@echo ""
	@echo "  auth0-mcp-surface — Agent Gateway OAuth Demo"
	@echo ""
	@echo "  make local-up        Run frontend (:5137) + backend (:$(PORT)) + MCP server (:$(MCP_PORT))"
	@echo "                       Auto-refreshes AWS SSO credentials for Bedrock LLM"
	@echo "  make backend         Chat backend only (honors backend/.env)"
	@echo "  make mcp             Chat MCP server only — the \`chat\` tool (:$(MCP_PORT))"
	@echo "                       Auto-refreshes AWS SSO credentials for Bedrock LLM"
	@echo "  make dev             Two-server hot-reload (frontend :5137 + backend :$(PORT))"
	@echo "  make local-down      Stop all services (frees :$(PORT), :5137, :$(MCP_PORT))"
	@echo "  make docker-up       Build + run the chat container (honors backend/.env)"
	@echo "  make docker-down     Stop the container"
	@echo ""
	@echo "  AWS Setup:"
	@echo "    - AWS SSO profile: $(AWS_PROFILE_NAME)"
	@echo "    - Override: AWS_PROFILE_NAME=your-profile make mcp"
	@echo "    - Alternative: Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN in mcp-server/.env"
	@echo ""

_preflight:
	@command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is required"; exit 1; }
	@command -v node    >/dev/null 2>&1 || { echo "ERROR: node is required"; exit 1; }

_build-frontend: _preflight
	@echo "→ Building frontend (single-origin: relative API base)…"
	cd frontend && npm install && PUBLIC_BACKEND_URL="" npm run build

_ensure-mcp-env:
	@if [ ! -f "mcp-server/.env" ]; then \
		echo "→ Creating mcp-server/.env from .env.example..."; \
		cp mcp-server/.env.example mcp-server/.env; \
	fi

_refresh-aws-creds: _ensure-mcp-env
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "🔐 Checking AWS credentials..."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@if [ -z "$(AWS_PROFILE_NAME)" ]; then \
		echo "ℹ️  No AWS_PROFILE_NAME set - MCP server will run in stub mode"; \
		echo "   (Returns mock responses instead of calling Bedrock)"; \
	elif aws sts get-caller-identity --profile "$(AWS_PROFILE_NAME)" > /dev/null 2>&1; then \
		echo "✓ AWS credentials still valid for profile: $(AWS_PROFILE_NAME)"; \
		echo "Exporting credentials to mcp-server/.env..."; \
		eval "$$(aws configure export-credentials --profile "$(AWS_PROFILE_NAME)" --format env)" && \
		if [ -n "$$AWS_ACCESS_KEY_ID" ]; then \
			grep -q '^AWS_ACCESS_KEY_ID=' mcp-server/.env && \
			sed -i '' 's|^AWS_ACCESS_KEY_ID=.*|AWS_ACCESS_KEY_ID='"$$AWS_ACCESS_KEY_ID"'|' mcp-server/.env || \
			echo "AWS_ACCESS_KEY_ID=$$AWS_ACCESS_KEY_ID" >> mcp-server/.env; \
			grep -q '^AWS_SECRET_ACCESS_KEY=' mcp-server/.env && \
			sed -i '' 's|^AWS_SECRET_ACCESS_KEY=.*|AWS_SECRET_ACCESS_KEY='"$$AWS_SECRET_ACCESS_KEY"'|' mcp-server/.env || \
			echo "AWS_SECRET_ACCESS_KEY=$$AWS_SECRET_ACCESS_KEY" >> mcp-server/.env; \
			grep -q '^AWS_SESSION_TOKEN=' mcp-server/.env && \
			sed -i '' 's|^AWS_SESSION_TOKEN=.*|AWS_SESSION_TOKEN='"$$AWS_SESSION_TOKEN"'|' mcp-server/.env || \
			echo "AWS_SESSION_TOKEN=$$AWS_SESSION_TOKEN" >> mcp-server/.env; \
			echo "✓ AWS credentials exported to mcp-server/.env"; \
		else \
			echo "⚠️  Failed to export credentials - continuing in stub mode"; \
			echo "   MCP server will run without Bedrock (returns mock responses)"; \
		fi; \
	else \
		echo "⚠️  AWS SSO session expired or profile not found - continuing in stub mode"; \
		echo "   Profile: $(AWS_PROFILE_NAME)"; \
		echo "   To use Bedrock: aws sso login --profile \"$(AWS_PROFILE_NAME)\""; \
		echo "   MCP server will run without Bedrock (returns mock responses)"; \
	fi

local-up: _refresh-aws-creds _build-frontend ## Run frontend (:5137) + chat backend (:$(PORT)) + chat MCP server (:$(MCP_PORT))
	@echo "→ frontend :5137 + chat backend :$(PORT) (backend/.env) + chat MCP server :$(MCP_PORT)"
	@echo "  Ctrl-C stops all three. Proxy each service separately for a public deploy."
	@bash -c 'trap "kill 0" EXIT INT TERM; \
	  ( cd backend && ([ -f .env ] || cp .env.example .env) && \
	    ([ -d .venv ] || python3 -m venv .venv) && \
	    .venv/bin/pip install --quiet -r requirements.txt && .venv/bin/python main.py ) & \
	  ( cd mcp-server && ./run.sh ) & \
	  ( cd frontend && npm run dev ) & \
	  wait'

backend: _build-frontend ## Chat backend only (honors backend/.env)
	@echo "→ Starting chat backend with backend/.env…"
	cd backend && \
	  ( [ -f .env ] || cp .env.example .env ) && \
	  ( [ -d .venv ] || python3 -m venv .venv ) && \
	  .venv/bin/pip install --quiet -r requirements.txt && \
	  .venv/bin/python main.py

mcp: _refresh-aws-creds _preflight ## Chat MCP server only (the `chat` tool) on :$(MCP_PORT)
	@echo "→ Chat MCP server on http://localhost:$(MCP_PORT)  (expose it, then register in the gateway)"
	cd mcp-server && ./run.sh

dev: _preflight ## Two-server hot-reload (frontend :5137 + backend :$(PORT))
	./dev.sh

local-down: ## Stop local-up / backend / mcp / dev processes
	@lsof -ti:$(PORT)     2>/dev/null | xargs kill 2>/dev/null || true
	@lsof -ti:5137        2>/dev/null | xargs kill 2>/dev/null || true
	@lsof -ti:$(MCP_PORT) 2>/dev/null | xargs kill 2>/dev/null || true
	@pkill -f "astro dev" 2>/dev/null || true
	@echo "stopped (freed :$(PORT), :5137, :$(MCP_PORT))."

docker-up: ## Build + run the chat container (honors backend/.env)
	docker compose up --build

docker-down: ## Stop the container
	docker compose down
