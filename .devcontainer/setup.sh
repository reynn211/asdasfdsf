#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

printf '[dev-setup] Preparing backend dependencies\n'

if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
  python3 -m venv "$BACKEND_DIR/.venv"
fi

"$BACKEND_DIR/.venv/bin/pip" install --upgrade pip
"$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt"

printf '[dev-setup] Preparing frontend dependencies\n'
(
  cd "$FRONTEND_DIR"
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
)

printf '[dev-setup] Done\n'
