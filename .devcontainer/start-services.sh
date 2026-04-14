#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUNTIME_DIR="$ROOT_DIR/.devcontainer/.runtime"
LOG_DIR="$RUNTIME_DIR/logs"
PID_DIR="$RUNTIME_DIR/pids"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

mkdir -p "$LOG_DIR" "$PID_DIR"

log() {
  printf '[dev-start] %s\n' "$1"
}

require_path() {
  local path="$1"
  local message="$2"

  if [[ ! -e "$path" ]]; then
    log "$message"
    exit 1
  fi
}

stop_service() {
  local pidfile="$1"
  local name="$2"
  local port="$3"

  if [[ -f "$pidfile" ]]; then
    kill "$(cat "$pidfile")" 2>/dev/null || true
    rm -f "$pidfile"
  fi

  if fuser "${port}/tcp" >/dev/null 2>&1; then
    log "Stopping process bound to port $port ($name)"
    fuser -k "${port}/tcp" >/dev/null 2>&1 || true
  fi
}

build_analyzer() {
  log "Compiling backend/analyzer.cpp"
  (
    cd "$BACKEND_DIR"
    g++ -std=c++17 -O2 -o analyzer analyzer.cpp
  )
}

start_backend() {
  log "Starting backend on port $BACKEND_PORT"
  (
    cd "$BACKEND_DIR"
    nohup ./.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT" \
      > "$LOG_DIR/backend.log" 2>&1 &
    echo $! > "$PID_DIR/backend.pid"
  )
}

start_frontend() {
  log "Starting frontend on port $FRONTEND_PORT"
  (
    cd "$FRONTEND_DIR"
    nohup ./node_modules/.bin/vite --host 0.0.0.0 --port "$FRONTEND_PORT" \
      > "$LOG_DIR/frontend.log" 2>&1 &
    echo $! > "$PID_DIR/frontend.pid"
  )
}

check_process() {
  local pidfile="$1"
  local name="$2"
  local logfile="$3"

  if [[ ! -f "$pidfile" ]]; then
    log "$name pid file was not created"
    exit 1
  fi

  local pid
  pid="$(cat "$pidfile")"

  if ! kill -0 "$pid" 2>/dev/null; then
    log "$name failed to start. Last log lines:"
    tail -n 40 "$logfile" || true
    exit 1
  fi
}

require_path "$BACKEND_DIR/.venv/bin/uvicorn" "Backend dependencies are missing. Run: bash .devcontainer/setup.sh"
require_path "$FRONTEND_DIR/node_modules/.bin/vite" "Frontend dependencies are missing. Run: bash .devcontainer/setup.sh"

stop_service "$PID_DIR/frontend.pid" "frontend" "$FRONTEND_PORT"
stop_service "$PID_DIR/backend.pid" "backend" "$BACKEND_PORT"
build_analyzer
start_backend
start_frontend

sleep 3

check_process "$PID_DIR/backend.pid" "backend" "$LOG_DIR/backend.log"
check_process "$PID_DIR/frontend.pid" "frontend" "$LOG_DIR/frontend.log"

log "Frontend: http://localhost:$FRONTEND_PORT"
log "Backend:  http://localhost:$BACKEND_PORT"
log "Logs: $LOG_DIR"
