"""
Minimal web UI backend for Trust Gateway load tests.

Run:
  pip install -r ui/requirements.txt
  python ui/server.py
  # Open http://localhost:5000
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading

from flask import Flask, Response, jsonify, request, send_from_directory

# ---------------------------------------------------------------------------
# Resolve binary paths
# ---------------------------------------------------------------------------
import sys as _sys

# locust lives in the same venv as this server; use the full path so the
# subprocess can find it even when the system PATH doesn't include the venv.
_VENV_BIN = os.path.dirname(os.path.abspath(_sys.executable))
_LOCUST_BIN = os.path.join(_VENV_BIN, 'locust')
if not os.path.isfile(_LOCUST_BIN):
    # Fall back to whatever is on PATH (e.g. global install)
    _LOCUST_BIN = 'locust'

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
_ANSI = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_UI_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=_UI_DIR)

_proc_lock = threading.Lock()
_current_proc: subprocess.Popen | None = None


def _strip_ansi(text: str) -> str:
    return _ANSI.sub('', text)


# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------
def _start(cmd: list[str], extra_env: dict | None = None):
    """Spawn a subprocess. Returns (proc, error_str)."""
    global _current_proc
    env = {**os.environ, **(extra_env or {})}
    with _proc_lock:
        if _current_proc and _current_proc.poll() is None:
            return None, "A test is already running. Stop it first."
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=_ROOT,
            env=env,
            bufsize=1,
        )
        _current_proc = proc
        return proc, None


def _stream(proc: subprocess.Popen):
    """
    Yield SSE events from the process stdout.
      REQUEST_JSON:{...}  →  event: request  (structured row for the results table)
      anything else       →  event: log      (plain text, shown in log panel)
    """
    global _current_proc
    try:
        for raw in proc.stdout:
            line = _strip_ansi(raw.rstrip())
            if not line:
                continue
            if line.startswith('REQUEST_JSON:'):
                payload = line[len('REQUEST_JSON:'):]
                yield f'event: request\ndata: {payload}\n\n'
            else:
                yield f'event: log\ndata: {json.dumps(line)}\n\n'
        proc.wait()
        yield f'event: done\ndata: {json.dumps({"exit": proc.returncode})}\n\n'
    except GeneratorExit:
        proc.terminate()
    finally:
        with _proc_lock:
            _current_proc = None


def _sse_response(cmd: list[str], extra_env: dict | None = None) -> Response:
    proc, err = _start(cmd, extra_env)
    if err:
        def _err_stream():
            yield f'event: log\ndata: {json.dumps("[ERROR] " + err)}\n\n'
            yield 'event: done\ndata: {"exit":1}\n\n'
        return Response(_err_stream(), mimetype='text/event-stream',
                        headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'})
    return Response(_stream(proc), mimetype='text/event-stream',
                    headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return send_from_directory(_UI_DIR, 'index.html')


@app.route('/api/config')
def api_config():
    """Return endpoints.json so the UI can render the endpoint list."""
    cfg = os.path.join(_ROOT, 'data', 'endpoints.json')
    with open(cfg) as f:
        return jsonify(json.load(f))


@app.route('/run/locust', methods=['POST'])
def run_locust():
    data = request.get_json(force=True) or {}
    extra_env: dict[str, str] = {}

    iterations = str(data.get('iterations') or '').strip()
    total_rps = str(data.get('totalRps') or '').strip()
    duration = str(data.get('duration') or '1m').strip()
    vus = str(data.get('vus') or '5').strip()

    # Endpoint filter: accept either a list (from Run page) or a single string
    endpoints = data.get('endpoints') or []
    endpoint = str(data.get('endpoint') or '').strip()
    if isinstance(endpoints, list) and endpoints:
        extra_env['ENDPOINTS'] = ','.join(str(e) for e in endpoints)
    elif endpoint:
        extra_env['ENDPOINTS'] = endpoint

    if total_rps:
        extra_env['TOTAL_RPS'] = total_rps
    if iterations:
        extra_env['ITERATIONS'] = iterations

    cmd = [
        _LOCUST_BIN, '-f', 'locust/locustfile.py',
        '--headless',
        '--users', vus,
        '--spawn-rate', vus,
        # Always supply --run-time; in iterations mode it acts as a safety cap.
        '--run-time', '24h' if iterations else duration,
    ]

    return _sse_response(cmd, extra_env)


@app.route('/stop', methods=['POST'])
def stop():
    with _proc_lock:
        proc = _current_proc
    if proc and proc.poll() is None:
        proc.terminate()
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'message': 'No running process'})


@app.route('/status')
def status():
    with _proc_lock:
        running = bool(_current_proc and _current_proc.poll() is None)
    return jsonify({'running': running})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    print("Load Test UI → http://127.0.0.1:9090")
    app.run(host='127.0.0.1', port=9090, debug=False, threaded=True)
