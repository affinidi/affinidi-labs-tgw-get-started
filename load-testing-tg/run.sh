#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

# ── 1. Locate python3 ────────────────────────────────────────────────────────
PYTHON=$(command -v python3 || command -v python || true)
if [[ -z "$PYTHON" ]]; then
  echo "ERROR: python3 not found. Install it with: brew install python" >&2
  exit 1
fi

# ── 2. Create virtualenv (once) ──────────────────────────────────────────────
if [[ ! -d "$VENV" ]]; then
  echo "Creating virtual environment at .venv …"
  "$PYTHON" -m venv "$VENV"
fi

PIP="$VENV/bin/pip"
PYEXE="$VENV/bin/python"

# ── 3. Install / upgrade dependencies ───────────────────────────────────────
echo "Installing dependencies …"
"$PIP" install --quiet --upgrade pip
"$PIP" install --quiet -r "$SCRIPT_DIR/ui/requirements.txt"
"$PIP" install --quiet -r "$SCRIPT_DIR/locust/requirements.txt"

# ── 4. Ensure endpoints.json exists ──────────────────────────────────────────
ENDPOINTS="$SCRIPT_DIR/data/endpoints.json"
TEMPLATE="$SCRIPT_DIR/data/endpoints.template.json"
if [[ ! -f "$ENDPOINTS" ]]; then
  echo ""
  echo "ERROR: data/endpoints.json not found."
  echo "  Copy the template and fill in your endpoints:"
  echo "    cp data/endpoints.template.json data/endpoints.json"
  echo ""
  exit 1
fi

# ── 5. Free port 9090 if in use ──────────────────────────────────────────────
PORT_PID=$(lsof -ti :9090 2>/dev/null || true)
if [[ -n "$PORT_PID" ]]; then
  echo "Killing process(es) on port 9090: $PORT_PID"
  echo "$PORT_PID" | xargs kill -9 2>/dev/null || true
  sleep 0.5
fi

# ── 6. Launch server ─────────────────────────────────────────────────────────
echo ""
echo "Starting Load Test UI → http://127.0.0.1:9090"
echo "Press Ctrl+C to stop."
echo ""

cd "$SCRIPT_DIR"
exec "$PYEXE" ui/server.py
