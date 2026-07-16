#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
#  auth0-mcp-surface / backend / run.sh
#
#  Usage:
#    ./run.sh          — create venv, install deps, start the FastAPI backend
#    ./run.sh help     — show this help
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
COMMAND="${1:-start}"

ensure_venv() {
  if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
  fi
  # shellcheck source=/dev/null
  source "$VENV_DIR/bin/activate"
}

load_env() {
  if [ -f ".env" ]; then
    set -o allexport
    # shellcheck source=/dev/null
    source .env
    set +o allexport
  fi
}

case "$COMMAND" in
  start|run)
    load_env
    ensure_venv
    echo "Installing dependencies..."
    pip install --quiet -r requirements.txt
    echo ""
    echo "Starting FastAPI backend on http://localhost:${PORT:-8000} ..."
    echo "Callback: ${REDIRECT_URI:-http://localhost:8000/api/auth/callback}"
    echo ""
    python3 main.py
    ;;
  help|--help|-h|"")
    echo ""
    echo "  auth0-mcp-surface backend — run.sh"
    echo "  Commands: start (default), help"
    echo ""
    ;;
  *)
    echo "Unknown command: $COMMAND"
    exit 1
    ;;
esac
