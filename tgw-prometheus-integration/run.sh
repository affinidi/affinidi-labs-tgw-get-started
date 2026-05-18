#!/usr/bin/env bash
# Trust Gateway → Prometheus → Grafana — bring-up script.
#
# Usage:
#   ./run.sh <TGW_HOST_1> [TGW_HOST_2 ...]
#       Recommended path. For each host:
#         • Derive an identifier from the host (strip the
#           STRIPPABLE_DOMAIN suffix; default ".affinidi.io").
#             acme-demo.trustgateway.affinidi.io → acme-demo.trustgateway
#             slug for job/dashboard → acme-demo-trustgateway
#         • Seed prometheus.yml from prometheus.yml.template if missing.
#         • Add (or replace) a scrape job named `tgw-<slug>` in the
#           BEGIN MANAGED / END MANAGED block of prometheus.yml.
#         • Generate `grafana/provisioning/dashboards/tgw-<slug>.json`
#           from dashboard-template.json.
#       Then start the stack.
#
#   ./run.sh
#       Start the stack with an already-prepared prometheus.yml and at
#       least one tgw-*.json dashboard. Fails with a guided message if
#       either is missing — use this only after manual editing.
#
# Override the strippable domain:
#   STRIPPABLE_DOMAIN=example.com ./run.sh tgw.example.com
#
# Accepted host forms (scheme/path/query are stripped):
#   tgw.example.com
#   https://tgw.example.com
#   https://tgw.example.com/api/v1/metrics/prometheus
#   tgw.example.com:8443
set -euo pipefail

cd "$(dirname "$0")"
CONF="prometheus.yml"
CONF_TEMPLATE="prometheus.yml.template"
DASH_DIR="grafana/provisioning/dashboards"
DASH_TEMPLATE="dashboard-template.json"
STRIPPABLE_DOMAIN="${STRIPPABLE_DOMAIN:-affinidi.io}"

# ── Helpers ──────────────────────────────────────────────────────────
usage() {
  sed -n '2,27p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

normalize_host() {
  local raw="$1"
  raw="${raw#http://}"
  raw="${raw#https://}"
  raw="${raw%%/*}"
  raw="${raw%%\?*}"
  raw="${raw%%#*}"
  raw="$(printf '%s' "$raw" | tr -d '[:space:]')"
  if [[ -z "$raw" ]]; then
    echo "❌ Could not extract host from input: '$1'" >&2
    exit 1
  fi
  printf '%s' "$raw"
}

# Strip the strippable suffix (default ".affinidi.io") plus any port.
# Returns the identifier — keeps the dots in the output (this is the
# `instance_name` label).  Example:
#   acme-demo.trustgateway.affinidi.io        → acme-demo.trustgateway
#   tgw.example.com  (suffix=example.com)   → tgw
#   localhost:9090                          → localhost
#   192.168.1.1                             → 192.168.1.1
host_to_identifier() {
  local host="$1"
  local suffix=".${STRIPPABLE_DOMAIN}"
  # strip port
  host="${host%%:*}"
  if [[ "$host" == *"$suffix" ]]; then
    host="${host%$suffix}"
  fi
  printf '%s' "$host"
}

# Slugify for use in job_name, dashboard filename, dashboard uid.
# Lowercase, replace dots and any non [a-z0-9-] with hyphens.
identifier_to_slug() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g'
}

# Render scrape_configs from the host list and update prometheus.yml.
render_scrape_configs() {
  python3 - "$CONF" "$STRIPPABLE_DOMAIN" "$@" <<'PY'
import re, sys, pathlib
path, suffix, *hosts = sys.argv[1], sys.argv[2], *sys.argv[3:]

def host_to_id(h):
    h = h.split(":", 1)[0]
    return h[:-len("." + suffix)] if h.endswith("." + suffix) else h

def slug(s):
    out = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return out or "tgw"

jobs = []
for h in hosts:
    ident = host_to_id(h)
    sl = slug(ident)
    jobs.append((sl, ident, h))

block_lines = []
for sl, ident, h in jobs:
    block_lines.append(f'  - job_name: "tgw-{sl}"')
    block_lines.append( '    scheme: https')
    block_lines.append( '    metrics_path: /api/v1/metrics/prometheus')
    block_lines.append( '    static_configs:')
    block_lines.append(f'      - targets: ["{h}"]')
    block_lines.append( '        labels:')
    block_lines.append(f'          instance_name: "{ident}"')
    block_lines.append('')  # blank line separating jobs
managed = (
    "  # ─── BEGIN MANAGED ───────────────────────────────────────────────────\n"
    + "\n".join(block_lines).rstrip() + "\n"
    + "  # ─── END MANAGED ─────────────────────────────────────────────────────"
)

text = pathlib.Path(path).read_text()
pattern = re.compile(
    r'  # ─── BEGIN MANAGED .*?# ─── END MANAGED [─]*',
    re.DOTALL,
)
if not pattern.search(text):
    print(f"❌ Could not find BEGIN MANAGED / END MANAGED markers in {path}", file=sys.stderr)
    sys.exit(1)
text = pattern.sub(lambda _: managed, text, count=1)
pathlib.Path(path).write_text(text)

# Emit slugs (one per line) for the bash side to know which dashboards
# to keep/generate.
for sl, ident, h in jobs:
    print(sl)
PY
}

generate_dashboard() {
  local slug="$1" ident="$2"
  local out="$DASH_DIR/tgw-${slug}.json"
  if [[ ! -f "$DASH_TEMPLATE" ]]; then
    echo "❌ Missing $DASH_TEMPLATE." >&2
    exit 1
  fi
  # Escape forward slashes in identifier for sed (paths shouldn't have any,
  # but be safe — use # as sed delimiter instead).
  sed -e "s#__JOB__#tgw-${slug}#g" \
      -e "s#__TITLE__#${ident}#g"  \
      -e "s#__UID__#tgw-${slug}#g" \
      "$DASH_TEMPLATE" > "$out"
  echo "   dashboard:       $out"
}

# ── Arg parsing ──────────────────────────────────────────────────────
case "${1:-}" in
  -h|--help) usage 0 ;;
esac

if [[ ! -f "$CONF_TEMPLATE" ]]; then
  echo "❌ $CONF_TEMPLATE not found in $(pwd)." >&2
  exit 1
fi

if [[ $# -ge 1 ]]; then
  # First-time (or post-clean) run: seed prometheus.yml from the template.
  if [[ ! -f "$CONF" ]]; then
    cp "$CONF_TEMPLATE" "$CONF"
    echo "▶ Created $CONF from $CONF_TEMPLATE."
  fi
  HOSTS=()
  echo "▶ Configuring Trust Gateways (strippable domain = $STRIPPABLE_DOMAIN):"
  for arg in "$@"; do
    H="$(normalize_host "$arg")"
    ID="$(host_to_identifier "$H")"
    SL="$(identifier_to_slug "$ID")"
    printf "   %-50s →  job=tgw-%s  label=%s\n" "$H" "$SL" "$ID"
    HOSTS+=("$H")
  done

  echo
  echo "▶ Updating $CONF:"
  SLUGS=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && SLUGS+=("$line")
  done < <(render_scrape_configs "${HOSTS[@]}")
  echo "   $CONF rewritten with ${#SLUGS[@]} scrape job(s)."

  echo
  echo "▶ Generating dashboards:"
  # 1. Create one dashboard per host.
  for i in "${!HOSTS[@]}"; do
    ID="$(host_to_identifier "$(normalize_host "${HOSTS[$i]}")")"
    generate_dashboard "${SLUGS[$i]}" "$ID"
  done
  # 2. Remove orphan tgw-*.json dashboards from previous runs.
  KEEP_SET=" $(printf 'tgw-%s.json ' "${SLUGS[@]}")"
  while IFS= read -r f; do
    name="$(basename "$f")"
    if [[ "$KEEP_SET" != *" $name "* ]]; then
      rm -f "$f"
      echo "   removed orphan: $f"
    fi
  done < <(find "$DASH_DIR" -maxdepth 1 -name 'tgw-*.json' -type f 2>/dev/null)
else
  # No args: require a manually-prepared prometheus.yml + at least one dashboard.
  MISSING=0
  if [[ ! -f "$CONF" ]]; then
    echo "❌ $CONF does not exist yet."
    MISSING=1
  elif grep -q "<your-subdomain>\|<your.tgw.host>" "$CONF"; then
    echo "❌ $CONF still contains <your-subdomain> / <your.tgw.host> placeholder(s)."
    MISSING=1
  fi
  if ! ls "$DASH_DIR"/tgw-*.json >/dev/null 2>&1; then
    echo "❌ No tgw-*.json dashboards in $DASH_DIR."
    MISSING=1
  fi
  if [[ $MISSING -eq 1 ]]; then
    cat >&2 <<EOF

Nothing to run yet. Choose one of:

  1. Easiest — let run.sh do everything:
        ./run.sh <TGW_HOST_1> [TGW_HOST_2 ...]

  2. Manual — copy the template, edit it, and generate dashboards yourself:
        cp $CONF_TEMPLATE $CONF
        \$EDITOR $CONF
        sed -e 's/__JOB__/tgw-<slug>/g' \\
            -e 's/__TITLE__/<label>/g'   \\
            -e 's/__UID__/tgw-<slug>/g'  \\
            $DASH_TEMPLATE > $DASH_DIR/tgw-<slug>.json
        ./run.sh
EOF
    exit 1
  fi
  echo "▶ Using $CONF as-is (no host arguments provided)."
fi

# ── Bring up the stack ───────────────────────────────────────────────
echo
echo "▶ Starting Prometheus + Grafana…"
docker compose up -d

# Hot-reload Prometheus in case it was already running.
docker compose kill -s HUP prometheus 2>/dev/null || true

echo
echo "▶ Waiting for services to be ready…"
for _ in {1..20}; do
  if curl -sf http://localhost:9090/-/ready >/dev/null && \
     curl -sf http://localhost:3000/api/health >/dev/null; then
    break
  fi
  sleep 1
done

echo
echo "▶ Scrape targets:"
curl -s http://localhost:9090/api/v1/targets | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
    [print(f\"  {t['labels']['job']:30s} {t['health']:8s} {t['scrapeUrl']}\") \
      for t in d['data']['activeTargets']]" 2>/dev/null || true

echo
echo "▶ Dashboards present:"
ls "$DASH_DIR"/tgw-*.json 2>/dev/null | sed 's|^|  |' || echo "  (none)"

cat <<EOF

✅ Stack is up.

  Prometheus  →  http://localhost:9090
  Grafana     →  http://localhost:3000   (admin / admin)

Open the "Trust Gateway" folder in Grafana to see the dashboards.

To stop:  docker compose down
EOF
