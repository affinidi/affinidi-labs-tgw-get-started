#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
#  test-agent-surface / run.sh
#
#  Usage:
#    ./run.sh              — start the OAuth chat app
#    ./run.sh start        — start the OAuth chat app
#    ./run.sh help         — show this help
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
COMMAND="${1:-start}"

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
  echo "    start        Start the Google OAuth + MCP Gateway chat UI"
  echo "    help         Show this help text"
  echo ""
}

# ── Commands ───────────────────────────────────────────────────────────────────

case "$COMMAND" in

  start|run)
    load_env
    ensure_venv
    install_deps requirements_ui.txt
    echo ""
    echo "Starting OAuth Chat UI on http://localhost:${PORT:-8081} ..."
    echo "Redirect URI: ${REDIRECT_URI:-http://localhost:8081/callback}"
    echo ""
    python3 oauth_chat_app.py
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
