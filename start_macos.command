#!/usr/bin/env bash
set -euo pipefail

cleanup() {
  code=$?
  if [ "$code" -ne 0 ]; then
    echo
    echo "Digital Clock failed with code $code."
    read -r -p "Press Enter to close..." _
  fi
}
trap cleanup EXIT

cd "$(dirname "$0")"

VENV_PY=".venv/bin/python3"

if [ ! -x "$VENV_PY" ]; then
  echo "[1/3] Creating virtual environment..."
  if command -v python3 >/dev/null 2>&1; then
    python3 -m venv .venv
  else
    echo "ERROR: python3 not found. Install Python 3.13+ and try again."
    exit 1
  fi
fi

echo "[2/3] Installing dependencies..."
"$VENV_PY" -m pip install --upgrade pip >/dev/null
"$VENV_PY" -m pip install -r requirements.txt

echo "[3/3] Launching Digital Clock..."
"$VENV_PY" main.py
