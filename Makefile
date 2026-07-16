# ──────────────────────────────────────────────────────────────────────────────
#  affinidi-labs-tgw-get-started — root Makefile
#
#  Convenience targets for the auth0-mcp-surface demo (Astro frontend + FastAPI
#  backend).
#    make local-up   → force LOCALHOST single-origin (ignores public .env vars)
#    make serve      → run whatever backend/.env says (deployment / public config)
#    make dev        → two-server hot reload
# ──────────────────────────────────────────────────────────────────────────────

APP_DIR         := auth0-mcp-surface
PORT            ?= 8642
PUBLIC_BASE_URL ?=

.DEFAULT_GOAL := help

.PHONY: help local-up serve dev local-down docker-up docker-down _preflight _build-frontend

help: ## Show available targets
	@echo ""
	@echo "  Agent Gateway chat surface — make targets"
	@echo ""
	@echo "  make local-up      LOCALHOST single-origin on :$(PORT) (forces localhost —"
	@echo "                     ignores PUBLIC_BASE_URL/FRONTEND_URL in .env)"
	@echo "                     → http://localhost:$(PORT)"
	@echo "  make serve         Run the config in backend/.env as-is (deployment /"
	@echo "                     public split). Uses PUBLIC_BASE_URL, FRONTEND_URL, etc."
	@echo "  make dev           Two-server hot-reload dev (frontend :5137 + backend :$(PORT))"
	@echo "  make local-down    Stop anything started by local-up / serve / dev"
	@echo "  make docker-up     Build + run the container (honors backend/.env)"
	@echo "  make docker-down   Stop the container"
	@echo ""

_preflight:
	@command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is required"; exit 1; }
	@command -v node    >/dev/null 2>&1 || { echo "ERROR: node is required"; exit 1; }

_build-frontend: _preflight
	@echo "→ Building frontend (single-origin: relative API base)…"
	cd $(APP_DIR)/frontend && npm install && PUBLIC_API_BASE="" npm run build

local-up: _build-frontend ## LOCALHOST single-origin on :$(PORT)
	@echo "→ Starting on http://localhost:$(PORT) (forced localhost single-origin)…"
	@echo "  (public .env vars are overridden; use 'make serve' for the deploy config)"
	cd $(APP_DIR)/backend && \
	  ( [ -d .venv ] || python3 -m venv .venv ) && \
	  .venv/bin/pip install --quiet -r requirements.txt && \
	  PORT=$(PORT) PUBLIC_BASE_URL="$(PUBLIC_BASE_URL)" FRONTEND_URL="" SESSION_COOKIE_DOMAIN="" \
	    .venv/bin/python main.py

serve: _build-frontend ## Run the config in backend/.env as-is (deployment / public)
	@echo "→ Starting backend with backend/.env (deployment config)…"
	cd $(APP_DIR)/backend && \
	  ( [ -f .env ] || cp .env.example .env ) && \
	  ( [ -d .venv ] || python3 -m venv .venv ) && \
	  .venv/bin/pip install --quiet -r requirements.txt && \
	  .venv/bin/python main.py

dev: _preflight ## Two-server hot-reload (frontend :5137 + backend :$(PORT))
	cd $(APP_DIR) && ./dev.sh

local-down: ## Stop local-up / serve / dev processes
	@lsof -ti:$(PORT) 2>/dev/null | xargs kill 2>/dev/null || true
	@lsof -ti:5137  2>/dev/null | xargs kill 2>/dev/null || true
	@pkill -f "astro dev" 2>/dev/null || true
	@echo "stopped (freed :$(PORT) and :5137)."

docker-up: ## Build + run the container (honors backend/.env)
	cd $(APP_DIR) && docker compose up --build

docker-down: ## Stop the container
	cd $(APP_DIR) && docker compose down
