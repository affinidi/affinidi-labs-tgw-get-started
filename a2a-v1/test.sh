#!/bin/bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

SERVER_URL="${1:-http://localhost:10001}"
if [[ ! -d venv ]]; then
    echo "Run ./run.sh once to create the virtual environment."
    exit 1
fi
source venv/bin/activate
python a2a_client.py "$SERVER_URL"