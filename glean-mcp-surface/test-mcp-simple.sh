#!/bin/bash

API_KEY=""
URL=""

do_request() {
  local body="$1"
  curl -s -w "\n__HTTP_STATUS__:%{http_code}" "$URL" \
    -H "Content-Type: application/json" \
    -H "Authorization: $API_KEY" \
    -d "$body"
}

parse_response() {
  local response="$1"
  HTTP_STATUS=$(echo "$response" | grep "__HTTP_STATUS__:" | cut -d: -f2)
  BODY=$(echo "$response" | sed '/__HTTP_STATUS__:/d')
}

handle_consent() {
  local body="$1"
  if [ "$HTTP_STATUS" = "401" ]; then
    AUTH_URL=$(echo "$body" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['consent_required'][0]['authorization_url'])" 2>/dev/null)
    if [ -n "$AUTH_URL" ]; then
      echo ""
      echo "=== Consent required ==="
      echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
      echo ""
      open "$AUTH_URL"
      read -rp "Press Enter after you have completed the login in the browser..."
      return 1  # signal: retry needed
    fi
  fi
  return 0
}

TOOLS_LIST_BODY='{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {
    "_meta": {
      "agentIdentity": {
        "name": "test-client",
        "version": "1.0.0"
      }
    }
  }
}'

echo "=== tools/list ==="
RESPONSE=$(do_request "$TOOLS_LIST_BODY")
parse_response "$RESPONSE"

if ! handle_consent "$BODY"; then
  echo "=== Retrying tools/list ==="
  RESPONSE=$(do_request "$TOOLS_LIST_BODY")
  parse_response "$RESPONSE"
fi

echo "HTTP Status: $HTTP_STATUS"
echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "Raw body: $BODY"

# ─── tools/call ───────────────────────────────────────────────────────────────

TOOLS_CALL_BODY='{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "_meta": {
      "agentIdentity": {
        "name": "test-client",
        "version": "1.0.0"
      }
    },
    "name": "search",
    "arguments": {
      "query": "onboarding"
    }
  }
}'

echo ""
echo "=== tools/call (search) ==="
RESPONSE=$(do_request "$TOOLS_CALL_BODY")
parse_response "$RESPONSE"

if ! handle_consent "$BODY"; then
  echo "=== Retrying tools/call ==="
  RESPONSE=$(do_request "$TOOLS_CALL_BODY")
  parse_response "$RESPONSE"
fi

echo "HTTP Status: $HTTP_STATUS"
echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "Raw body: $BODY"

