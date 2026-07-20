#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
#  auth0-mcp-surface / dev.sh — run backend (FastAPI) and frontend (Astro) together
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
  echo ""
  echo "Shutting down…"
  kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting FastAPI backend (:8642)…"
( cd "$SCRIPT_DIR/backend" && ./run.sh ) &

echo "Starting Astro frontend (:5137)…"
( cd "$SCRIPT_DIR/frontend" && npm run dev ) &

wait
