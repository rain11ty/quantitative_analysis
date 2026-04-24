#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"

PYTHON_EXE="python3"
if [ -x ".venv/bin/python" ]; then
    PYTHON_EXE=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then
    PYTHON_EXE="venv/bin/python"
fi

echo "Starting Stock Analysis Web App..."
echo
echo "Python : ${PYTHON_EXE}"
echo "URL    : http://127.0.0.1:5001"
echo
echo "Tip: install dependencies manually if this is the first run."
echo "Example: pip install -r requirements.txt"
echo

exec "${PYTHON_EXE}" quick_start.py
