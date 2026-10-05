#!/bin/bash
set -euo pipefail

SERVER_URL="${1:-http://localhost:10001}"
if [[ ! -d venv ]]; then
    echo "Run ./run.sh once to create the virtual environment."
    exit 1
fi
source venv/bin/activate
python smoke_test.py "$SERVER_URL"