#!/usr/bin/env sh
# One-shot, idempotent project setup (macOS/Linux/Git Bash).
set -eu
export PIP_REQUIRE_VIRTUALENV=1   # pip refuses to install outside a venv
cd "$(dirname "$0")"

[ -d .venv ] || python3 -m venv .venv
if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe; else PY=.venv/bin/python; fi
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r backend/requirements-dev.txt

[ -f .env ] || cp .env.example .env
[ -f frontend/package.json ] && (cd frontend && npm install)

echo "Done. Activate with: source .venv/bin/activate (Windows: .venv/Scripts/activate)"
