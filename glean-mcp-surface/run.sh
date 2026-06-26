#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
#  test-agent-surface / run.sh
#
#  Usage:
#    ./run.sh              — show this help
#    ./run.sh ui           — start the Google OAuth chat UI (port 8081)
#    ./run.sh ngrok        — start a new ngrok tunnel for the OAuth callback
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
COMMAND="${1:-help}"

# ── Helpers ────────────────────────────────────────────────────────────────────

ensure_venv() {
  if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
  fi
  # shellcheck source=/dev/null
  source "$VENV_DIR/bin/activate"
}

install_deps() {
  local req_file="$1"
  echo "Installing dependencies from $req_file ..."
  pip install --quiet -r "$req_file"
}

load_env() {
  if [ -f ".env" ]; then
    set -o allexport
    # shellcheck source=/dev/null
    source .env
    set +o allexport
  fi
}

print_help() {
  echo ""
  echo "  test-agent-surface — run.sh"
  echo ""
  echo "  Commands:"
  echo "    ui           Start the Google OAuth + MCP Gateway chat UI"
  echo "    ngrok        Start a ngrok tunnel for the OAuth redirect URI"
  echo ""
  echo "  Environment variables are loaded from .env automatically."
  echo ""
}

# ── Commands ───────────────────────────────────────────────────────────────────

case "$COMMAND" in

  ui)
    load_env
    ensure_venv
    install_deps requirements_ui.txt
    echo ""
    echo "Starting OAuth Chat UI on http://localhost:${PORT:-8081} ..."
    echo "Redirect URI: ${REDIRECT_URI:-http://localhost:8081/callback}"
    echo ""
    python3 oauth_chat_app.py
    ;;

  ngrok)
    load_env
    ensure_venv
    install_deps requirements_ui.txt
    TOKEN="${NGROK_AUTH_TOKEN:-${2:-}}"
    if [ -z "$TOKEN" ]; then
      echo "ERROR: NGROK_AUTH_TOKEN is not set."
      echo "  Set it in .env or pass as argument: ./run.sh ngrok <token>"
      exit 1
    fi
    echo ""
    echo "Starting ngrok tunnel → localhost:${PORT:-8081} ..."
    python3 ngrok_tunnel.py "$TOKEN" "${PORT:-8081}"
    ;;

  help|--help|-h|"")
    print_help
    ;;

  *)
    echo "Unknown command: $COMMAND"
    print_help
    exit 1
    ;;

esac
