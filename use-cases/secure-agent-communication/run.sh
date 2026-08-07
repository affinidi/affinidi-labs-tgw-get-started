#!/usr/bin/env bash
# =============================================================================
# run.sh — Secure Agent Communication
# =============================================================================
# Usage:
#   ./run.sh          → kill portal ports + restart portals (agents kept if running)
#   ./run.sh force    → kill ALL ports + start everything fresh
#   ./run.sh stop     → kill all ports (agents + portals)
#   ./run.sh status   → show what is running on known ports
#   ./run.sh logs     → tail all log files
# =============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$ROOT/.logs"

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[info]${RESET}  $*"; }
success() { echo -e "${GREEN}[ok]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[warn]${RESET}  $*"; }
error()   { echo -e "${RED}[error]${RESET} $*" >&2; }
header()  { echo -e "\n${BOLD}$*${RESET}"; }

ORG_A_AGENT_PORT=$(grep -E  '^AGENT_PORT='  "$ROOT/org-a.env" | cut -d= -f2 | tr -d '"' || echo "8001")
ORG_B_AGENT_PORT=$(grep -E  '^AGENT_PORT='  "$ROOT/org-b.env" | cut -d= -f2 | tr -d '"' || echo "8011")
ORG_A_PORTAL_PORT=$(grep -E '^PORTAL_PORT=' "$ROOT/org-a.env" | cut -d= -f2 | tr -d '"' || echo "3001")
ORG_B_PORTAL_PORT=$(grep -E '^PORTAL_PORT=' "$ROOT/org-b.env" | cut -d= -f2 | tr -d '"' || echo "3002")

kill_by_port() {
  local port="$1"
  local pids
  pids=$(lsof -ti:"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -9 2>/dev/null || true
    info "Killed port $port"
  fi
}

check_prerequisites() {
  command -v python3 &>/dev/null || { error "python3 not found"; exit 1; }
  command -v node   &>/dev/null || { error "node not found";    exit 1; }
  command -v npm    &>/dev/null || { error "npm not found";     exit 1; }
}

# Auto-create env files from examples if they don't exist
init_env() {
  local created=0
  for org in a b; do
    if [ ! -f "$ROOT/org-${org}.env" ]; then
      cp "$ROOT/org-${org}.env.example" "$ROOT/org-${org}.env"
      success "Created org-${org}.env from org-${org}.env.example"
      created=1
    fi
  done
  if [ "$created" -eq 1 ]; then
    echo ""
    warn "env files created from examples with localhost defaults."
    warn "Edit org-a.env and org-b.env if you need to change agent URLs or add Entra credentials."
    echo ""
  fi
}

setup() {
  if [ ! -d "$ROOT/agent/venv" ]; then
    header "Setting up Python venv..."
    python3 -m venv "$ROOT/agent/venv"
    "$ROOT/agent/venv/bin/pip" install -q --upgrade pip
    "$ROOT/agent/venv/bin/pip" install -q -r "$ROOT/agent/requirements.txt"
    success "Agent venv ready"
  fi
  if [ ! -d "$ROOT/portal/node_modules" ]; then
    header "Installing portal npm dependencies..."
    (cd "$ROOT/portal" && npm install --silent)
    success "Portal dependencies installed"
  fi
}

start_agents() {
  header "Starting Org A — Thatcher Agent (port $ORG_A_AGENT_PORT)..."
  (set -a; source "$ROOT/org-a.env"; set +a
   "$ROOT/agent/venv/bin/python" "$ROOT/agent/agent.py") \
    > "$LOGS_DIR/org-a-agent.log" 2>&1 &
  success "Thatcher Agent started (pid $!)"

  header "Starting Org B — Dexter Agent (port $ORG_B_AGENT_PORT)..."
  (set -a; source "$ROOT/org-b.env"; set +a
   "$ROOT/agent/venv/bin/python" "$ROOT/agent/agent.py") \
    > "$LOGS_DIR/org-b-agent.log" 2>&1 &
  success "Dexter Agent started (pid $!)"
}

start_portals() {
  rm -rf "$ROOT/portal/.next-org-a" "$ROOT/portal/.next-org-b"

  header "Starting Org A Portal (port $ORG_A_PORTAL_PORT)..."
  (set -a; source "$ROOT/org-a.env"; set +a
   cd "$ROOT/portal"
   NEXT_DIST_DIR=.next-org-a npx --yes next dev -p "${PORTAL_PORT:-3001}") \
    > "$LOGS_DIR/org-a-portal.log" 2>&1 &
  success "Org A Portal started (pid $!)"

  header "Starting Org B Portal (port $ORG_B_PORTAL_PORT)..."
  (set -a; source "$ROOT/org-b.env"; set +a
   cd "$ROOT/portal"
   NEXT_DIST_DIR=.next-org-b npx --yes next dev -p "${PORTAL_PORT:-3002}") \
    > "$LOGS_DIR/org-b-portal.log" 2>&1 &
  success "Org B Portal started (pid $!)"
}

print_urls() {
  echo ""
  echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${RESET}"
  echo -e "${BOLD}║           Secure Agent Communication                 ║${RESET}"
  echo -e "${BOLD}╠══════════════════════════════════════════════════════╣${RESET}"
  echo -e "${BOLD}║  Org A (Thatcher)                                    ║${RESET}"
  echo -e "║    Portal  → ${GREEN}http://localhost:${ORG_A_PORTAL_PORT}${RESET}                   ║"
  echo -e "║    Agent   → ${CYAN}http://localhost:${ORG_A_AGENT_PORT}${RESET}                   ║"
  echo -e "${BOLD}╠══════════════════════════════════════════════════════╣${RESET}"
  echo -e "${BOLD}║  Org B (Dexter)                                      ║${RESET}"
  echo -e "║    Portal  → ${GREEN}http://localhost:${ORG_B_PORTAL_PORT}${RESET}                   ║"
  echo -e "║    Agent   → ${CYAN}http://localhost:${ORG_B_AGENT_PORT}${RESET}                   ║"
  echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${RESET}"
  echo ""
  info "Portals take ~15s to compile on first run. Logs: $LOGS_DIR/"
}

CMD="${1:-start}"
case "$CMD" in
  start|"")
    check_prerequisites
    init_env
    # Kill portal ports only — agents keep running if already up
    kill_by_port "$ORG_A_PORTAL_PORT"
    kill_by_port "$ORG_B_PORTAL_PORT"
    sleep 1
    # Start agents only if not already running
    if ! lsof -ti:"$ORG_A_AGENT_PORT" &>/dev/null; then
      mkdir -p "$LOGS_DIR"; setup; start_agents; sleep 1
    else
      info "Agents already running — skipping agent start"
    fi
    mkdir -p "$LOGS_DIR"
    start_portals
    print_urls
    ;;
  stop)
    kill_by_port "$ORG_A_AGENT_PORT"
    kill_by_port "$ORG_B_AGENT_PORT"
    kill_by_port "$ORG_A_PORTAL_PORT"
    kill_by_port "$ORG_B_PORTAL_PORT"
    success "All services stopped"
    ;;
  force)
    check_prerequisites
    kill_by_port "$ORG_A_AGENT_PORT"
    kill_by_port "$ORG_B_AGENT_PORT"
    kill_by_port "$ORG_A_PORTAL_PORT"
    kill_by_port "$ORG_B_PORTAL_PORT"
    sleep 2
    mkdir -p "$LOGS_DIR"
    setup
    start_agents
    sleep 1
    start_portals
    print_urls
    ;;
  status)
    for entry in \
      "Thatcher Agent:$ORG_A_AGENT_PORT" \
      "Dexter Agent:$ORG_B_AGENT_PORT" \
      "Org A Portal:$ORG_A_PORTAL_PORT" \
      "Org B Portal:$ORG_B_PORTAL_PORT"; do
      name="${entry%%:*}"; port="${entry##*:}"
      pids=$(lsof -ti:"$port" 2>/dev/null || true)
      if [ -n "$pids" ]; then
        success "$name (port $port) — running"
      else
        warn "$name (port $port) — not running"
      fi
    done
    ;;
  logs)
    [ -d "$LOGS_DIR" ] && tail -f "$LOGS_DIR"/*.log || warn "No logs yet"
    ;;
  *)
    error "Unknown command: $CMD"
    echo "Usage: $0 [start|stop|status|logs]"
    exit 1
    ;;
esac
