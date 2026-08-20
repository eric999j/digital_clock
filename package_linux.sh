#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

VENV_PY=".venv/bin/python3"

if [ ! -x "$VENV_PY" ]; then
  echo "[1/4] Creating virtual environment..."
  if command -v python3 >/dev/null 2>&1; then
    python3 -m venv .venv
  else
    echo "ERROR: python3 not found. Install Python 3.13+ and try again."
    exit 1
  fi
fi

echo "[2/4] Installing runtime dependencies..."
"$VENV_PY" -m pip install --upgrade pip >/dev/null
"$VENV_PY" -m pip install -r requirements.txt

echo "[3/4] Installing packaging tools..."
"$VENV_PY" -m pip install --upgrade pyinstaller

echo "[4/4] Building release binary..."
"$VENV_PY" -m PyInstaller --noconfirm --clean --windowed --onefile --name DigitalClock --collect-all pynput main.py

echo
echo "Build completed: dist/DigitalClock"
echo "You can launch this binary directly on Linux."
