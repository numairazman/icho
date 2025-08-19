#!/usr/bin/env bash
# ======================================================
# Icho launcher for Linux/macOS
# - Ensures local venv (.venv) exists
# - Installs requirements if needed
# - Runs main.py
# ======================================================

set -euo pipefail

# Jump to project root (one level up from scripts/)
cd "$(dirname "$0")/.."

# Pick a python
PYBIN="${PYBIN:-python3}"
if ! command -v "$PYBIN" >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then
    PYBIN="python"
  else
    echo "[Icho] ERROR: python3/python not found in PATH." >&2
    exit 1
  fi
fi

# ---------- Detect or create venv ----------
if [[ -x ".venv/bin/python" ]]; then
  echo "[Icho] Using existing venv: .venv"
else
  echo "[Icho] Creating virtual environment (.venv)..."
  "$PYBIN" -m venv .venv
fi

# ---------- Activate venv ----------
# shellcheck disable=SC1091
source ".venv/bin/activate"

# ---------- Ensure pip & deps ----------
echo "[Icho] Upgrading pip (safe to skip if offline)..."
python -m pip install --upgrade pip >/dev/null 2>&1 || true

if [[ -f "requirements.txt" ]]; then
  echo "[Icho] Installing/upgrading dependencies from requirements.txt..."
  pip install -r requirements.txt
else
  echo "[Icho] WARNING: requirements.txt not found; continuing..."
fi

# ---------- Run the app ----------
echo "[Icho] Launching Icho..."
exec python main.py