# ──────────────────────────────────────────────────────────────────────────────
#  affinidi-labs-tgw-get-started — root Makefile
#
#  Convenience targets for the auth0-mcp-surface demo (Astro frontend + FastAPI
#  backend). local-up / docker-up run it single-origin on ONE port so it is
#  trivial to forward or tunnel (ngrok / Codespaces).
# ──────────────────────────────────────────────────────────────────────────────

APP_DIR         := auth0-mcp-surface
PORT            ?= 8642
PUBLIC_BASE_URL ?=

.DEFAULT_GOAL := help

.PHONY: help local-up dev local-down docker-up docker-down _preflight _build-frontend

help: ## Show available targets
	@echo ""
	@echo "  Agent Gateway chat surface — make targets"
	@echo ""
	@echo "  make local-up      Build the frontend and run the app single-origin on :$(PORT)"
	@echo "                     → http://localhost:$(PORT)"
	@echo "                     Public URL: make local-up PUBLIC_BASE_URL=https://<host>"
	@echo "  make dev           Two-server hot-reload dev (frontend :5137 + backend :8642)"
	@echo "  make local-down    Stop anything started by local-up / dev"
	@echo "  make docker-up     Build + run the single container (docker compose)"
	@echo "  make docker-down   Stop the container"
	@echo ""

_preflight:
	@command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is required"; exit 1; }
	@command -v node    >/dev/null 2>&1 || { echo "ERROR: node is required"; exit 1; }

_build-frontend: _preflight
	@echo "→ Building frontend (single-origin: relative API base)…"
	cd $(APP_DIR)/frontend && npm install && PUBLIC_API_BASE="" npm run build

local-up: _build-frontend ## Build frontend + run single-origin on :$(PORT)
	@echo "→ Starting app on http://localhost:$(PORT) (single origin: API + static)…"
	@if [ -n "$(PUBLIC_BASE_URL)" ]; then echo "→ Public base URL: $(PUBLIC_BASE_URL)"; fi
	cd $(APP_DIR)/backend && \
	  ( [ -f .env ] || cp .env.example .env ) && \
	  ( [ -d .venv ] || python3 -m venv .venv ) && \
	  .venv/bin/pip install --quiet -r requirements.txt && \
	  PORT=$(PORT) PUBLIC_BASE_URL="$(PUBLIC_BASE_URL)" .venv/bin/python main.py

dev: _preflight ## Two-server hot-reload (frontend :5137 + backend :8642)
	cd $(APP_DIR) && ./dev.sh

local-down: ## Stop local-up / dev processes
	@lsof -ti:$(PORT) 2>/dev/null | xargs kill 2>/dev/null || true
	@lsof -ti:5137  2>/dev/null | xargs kill 2>/dev/null || true
	@pkill -f "astro dev" 2>/dev/null || true
	@echo "stopped (freed :$(PORT) and :5137)."

docker-up: ## Build + run the single container
	cd $(APP_DIR) && docker compose up --build

docker-down: ## Stop the container
	cd $(APP_DIR) && docker compose down
