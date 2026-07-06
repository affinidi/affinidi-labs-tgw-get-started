"""
Agent Gateway load test — Locust edition.

Mirrors the k6 harness (k6/load-test.js):
  - Reads data/endpoints.json (shared endpoint configuration)
  - Two-level random selection: endpoint first, then variant within endpoint
    → every active endpoint receives an equal share of requests regardless of
      how many calls it defines
  - ITERATIONS mode  : run exactly N requests total, then stop
  - Rate mode        : run at constant RPS for a fixed duration

Run examples
------------
  # Install once
  pip install -r locust/requirements.txt

  # 100 requests, 5 parallel users (ITERATIONS mode)
  ITERATIONS=100 locust --headless --users 5 --spawn-rate 5 --run-time 24h -f locust/locustfile.py

  # ~10 req/s for 1 minute (rate mode: 1 req/s per user × 10 users)
  TOTAL_RPS=10 locust --headless --users 10 --spawn-rate 10 --run-time 1m -f locust/locustfile.py

  # Single smoke request
  ITERATIONS=1 locust --headless --users 1 --spawn-rate 1 --run-time 24h -f locust/locustfile.py

  # Open web UI (http://localhost:8089)
  locust -f locust/locustfile.py

Environment variables
---------------------
  ITERATIONS   Run exactly this many requests total, then stop (overrides rate mode)
  TOTAL_RPS    Target requests/second; set --users to match so each user does 1 req/s
  CONFIG       Path to config JSON (default: data/endpoints.json)
  LOG_ERRORS   Max non-2xx responses to log per endpoint (default: 3)
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
import uuid
from collections import defaultdict

from locust import HttpUser, constant_throughput, events, task
from locust.exception import StopUser
from locust.env import Environment

# ---------------------------------------------------------------------------
# Load config
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.environ.get(
    "CONFIG", os.path.join(_HERE, "../data/endpoints.json"))

with open(os.path.abspath(_CONFIG_PATH)) as _f:
    _raw_config = json.load(_f)

_TOTAL_RPS = int(os.environ.get("TOTAL_RPS", 0))
_MAX_ERROR_LOGS = int(os.environ.get("LOG_ERRORS", 3))
# 0 = unlimited (rate/duration mode)
_MAX_ITERS = int(os.environ.get("ITERATIONS", 0))
_iter_claimed = 0   # slots claimed before a request is sent
_iter_done = 0   # requests that have fully completed
_iter_lock = threading.Lock()
_locust_env = None  # captured at test_start; used to call runner.quit()


@events.test_start.add_listener
def _on_test_start(environment, **_kw) -> None:
    global _locust_env, _iter_claimed, _iter_done
    _locust_env = environment
    _iter_claimed = 0
    _iter_done = 0


# ENDPOINTS (comma-separated) or ENDPOINT (single) restrict which endpoints are tested.
# Both are set by the UI; ENDPOINTS takes priority.
_raw_ep_filter = os.environ.get(
    "ENDPOINTS") or os.environ.get("ENDPOINT") or None

# ---------------------------------------------------------------------------
# Build variant pool (same logic as k6/load-test.js)
# ---------------------------------------------------------------------------
#: endpoint_name -> list of variant dicts
VARIANTS_BY_ENDPOINT: dict[str, list[dict]] = {}
#: ordered list of active endpoint names
ENDPOINT_NAMES: list[str] = []

for _ep in _raw_config["endpoints"]:
    if _ep.get("active") is False:
        print(f"[config] skipping inactive endpoint: {_ep['name']}")
        continue

    _name = _ep["name"]
    ENDPOINT_NAMES.append(_name)
    VARIANTS_BY_ENDPOINT[_name] = []

    if _ep["type"] == "a2a":
        for _i, _msg in enumerate(_ep.get("messages", [])):
            VARIANTS_BY_ENDPOINT[_name].append(
                {
                    "endpoint": _name,
                    "type": "a2a",
                    "url": _ep["url"],
                    "variant": f"msg_{_i}",
                    "a2aText": _msg,
                    "headers": _ep.get("headers") or {},
                }
            )
    elif _ep["type"] == "mcp":
        for _i, _call in enumerate(_ep.get("calls", [])):
            _tool = (_call.get("params") or {}).get("name")
            _label = f"{_call['method']}:{_tool}" if _tool else f"{_call['method']}#{_i}"
            VARIANTS_BY_ENDPOINT[_name].append(
                {
                    "endpoint": _name,
                    "type": "mcp",
                    "url": _ep["url"],
                    "variant": _label,
                    "mcpMethod": _call["method"],
                    "mcpParams": _call.get("params") or {},
                    "headers": _ep.get("headers") or {},
                }
            )
    else:
        raise ValueError(
            f"endpoint '{_name}' has unknown type '{_ep['type']}'")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _unique_id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"


def _build_body(v: dict) -> dict:
    if v["type"] == "a2a":
        return {
            "jsonrpc": "2.0",
            "id": _unique_id(v["endpoint"]),
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": v["a2aText"]}],
                    "messageId": _unique_id("msg"),
                }
            },
        }
    return {
        "jsonrpc": "2.0",
        "id": _unique_id(v["endpoint"]),
        "method": v["mcpMethod"],
        "params": v["mcpParams"],
    }


def _pick_variant() -> dict:
    """Two-level selection: endpoint first (uniform), then variant within it.
    Respects ENDPOINTS / ENDPOINT env var filter set by the UI.
    """
    # Build allowed list lazily after VARIANTS_BY_ENDPOINT is populated.
    # _raw_ep_filter is a comma-separated string or None.
    if _raw_ep_filter:
        allowed = [
            e.strip() for e in _raw_ep_filter.split(",")
            if e.strip() in VARIANTS_BY_ENDPOINT
        ]
        if not allowed:
            raise ValueError(
                f"No matching active endpoints for filter: {_raw_ep_filter!r}")
        ep_name = random.choice(allowed)
    else:
        ep_name = random.choice(ENDPOINT_NAMES)
    return random.choice(VARIANTS_BY_ENDPOINT[ep_name])


# ---------------------------------------------------------------------------
# Iteration counter — shared across all VUs (ITERATIONS mode only)
# ---------------------------------------------------------------------------
# Per-endpoint error logger (limits log spam)
# ---------------------------------------------------------------------------
_error_log_counts: dict[str, int] = defaultdict(int)
_error_log_lock = threading.Lock()


def _log_error(v: dict, status: int, body: str) -> None:
    with _error_log_lock:
        if _error_log_counts[v["endpoint"]] >= _MAX_ERROR_LOGS:
            return
        _error_log_counts[v["endpoint"]] += 1
    snippet = body[:300].replace("\n", " ")
    print(
        f"[err] {v['endpoint']} variant={v['variant']} "
        f"status={status} body=\"{snippet}\""
    )


# ---------------------------------------------------------------------------
# Per-request event hook — emits structured JSON lines parsed by the UI server
# ---------------------------------------------------------------------------
@events.request.add_listener
def _on_request(
    request_type: str,
    name: str,
    response_time: float,
    response_length: int,
    response: object,
    exception: Exception | None,
    **_kw: object,
) -> None:
    status = 0
    if response is not None and hasattr(response, "status_code"):
        status = response.status_code  # type: ignore[union-attr]
    ok = exception is None and 200 <= status < 300
    parts = name.split(":", 1)
    record = {
        "endpoint": parts[0],
        "variant":  parts[1] if len(parts) > 1 else "",
        "status":   status,
        "latency":  round(response_time),
        "ok":       ok,
        "ts":       time.strftime("%H:%M:%S"),
    }
    # PREFIX allows the Flask server to distinguish structured data from plain logs
    print(f"REQUEST_JSON:{json.dumps(record)}", flush=True)

    # In iterations mode: quit the runner once every expected request has completed.
    # We quit here (post-completion) so no in-flight requests are killed.
    if _MAX_ITERS > 0 and _locust_env is not None:
        import gevent
        with _iter_lock:
            global _iter_done
            _iter_done += 1
            should_quit = (_iter_done >= _MAX_ITERS)
        if should_quit:
            gevent.spawn_later(0.2, _locust_env.runner.quit)


# ---------------------------------------------------------------------------
# Locust user
# ---------------------------------------------------------------------------
class TrustGatewayUser(HttpUser):
    # Full URLs are supplied per-request; host is intentionally empty.
    # Pass --host "" on the CLI if Locust complains, or just let the
    # class attribute take precedence.
    host = ""

    # Rate mode: each user targets 1 req/s so total RPS == --users count.
    # In iterations mode Locust's own --iterations flag controls the budget.
    if _TOTAL_RPS:
        # 1 req/s per user; set --users=TOTAL_RPS
        wait_time = constant_throughput(1)

    @task
    def send_request(self) -> None:
        global _iter_claimed
        # Claim a slot before sending; if all slots taken, stop this user.
        # runner.quit() is called from _on_request once the last request completes.
        if _MAX_ITERS > 0:
            with _iter_lock:
                if _iter_claimed >= _MAX_ITERS:
                    raise StopUser()
                _iter_claimed += 1
        v = _pick_variant()
        name = f"{v['endpoint']}:{v['variant']}"

        with self.client.post(
            v["url"],
            json=_build_body(v),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                **(v.get("headers") or {}),
            },
            timeout=30,
            name=name,
            catch_response=True,
        ) as resp:
            if resp.status_code < 200 or resp.status_code >= 300:
                resp.failure(f"HTTP {resp.status_code}")
                _log_error(v, resp.status_code, resp.text or "")
            else:
                resp.success()


# ---------------------------------------------------------------------------
# Summary (printed after the test)
# ---------------------------------------------------------------------------
@events.quitting.add_listener
def _print_summary(environment: Environment, **_kw: object) -> None:
    stats = environment.stats
    total = stats.total

    print("\n=== Load Test Summary ===")
    print(f"Total requests : {total.num_requests}")

    fail_rate = total.num_failures / max(total.num_requests, 1) * 100
    print(f"Failed rate    : {fail_rate:.2f}%")

    p95 = total.get_response_time_percentile(0.95) or 0
    print(f"Latency avg/p95: {total.avg_response_time:.1f} / {p95:.1f} ms")
    print()

    for ep in ENDPOINT_NAMES:
        ep_reqs = ep_fail = 0
        ep_p95 = 0.0
        for entry in stats.entries.values():
            if entry.name.startswith(f"{ep}:"):
                ep_reqs += entry.num_requests
                ep_fail += entry.num_failures
                p = entry.get_response_time_percentile(0.95) or 0
                ep_p95 = max(ep_p95, p)
        err_pct = ep_fail / max(ep_reqs, 1) * 100
        print(f"- {ep:<16}  reqs={ep_reqs}  err={err_pct:.2f}%  p95={ep_p95:.1f}ms")

    print()
