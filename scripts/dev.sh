#!/usr/bin/env bash
# Run the whole app locally, no Docker.
#
# Why this exists: the Docker path needs a ~4 GB image (torch dominates) and a
# 67 GB Docker VM, and on this machine the VM's filesystem is corrupt (blob
# reads fail with EIO), so the daemon no longer starts. This path needs neither.
#
#   ./scripts/dev.sh          start postgres + backend + frontend
#   ./scripts/dev.sh stop     stop backend + frontend
#   ./scripts/dev.sh status   report what is up
#
set -uo pipefail
cd "$(dirname "$0")/.."

VENV=./venv
PGVER=15
PGPORT=5434
DB=codebase_rag
BACKEND=http://127.0.0.1:8001
waited() { sleep "$1"; }

# Waiting for the port to actually free before rebinding is what keeps an
# interrupted run from leaving the stack half-down: a kill followed by an
# immediate start races the old listener and the new one never binds.
free_port() {
  for _ in $(seq 1 30); do
    lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1 || return 0
    waited 1
  done
  return 1
}

healthy() { curl -s -m 2 -o /dev/null "$1"; }

wait_healthy() {
  local url=$1 tries=${2:-60} log=${3:-}
  for _ in $(seq 1 "$tries"); do
    healthy "$url" && return 0
    waited 1
  done
  echo "  !! $url never became healthy" >&2
  [ -n "$log" ] && [ -f "$log" ] && { echo "  --- last lines of $log ---" >&2; tail -15 "$log" >&2; }
  return 1
}

status() {
  printf '  postgres  %s:%s  ' "$PGPORT" "$DB"
  pg_isready -h localhost -p $PGPORT >/dev/null 2>&1 && echo "up" || echo "DOWN"
  printf '  backend   %s  ' "$BACKEND"
  healthy "$BACKEND/health" && echo "up" || echo "DOWN"
  printf '  frontend  http://localhost:5173  '
  healthy http://localhost:5173 && echo "up" || echo "DOWN"
}

start() {
  echo "==> postgres (postgresql@$PGVER on $PGPORT, provides the pgvector extension)"
  brew services start postgresql@$PGVER >/dev/null 2>&1 || true
  pg_isready -h localhost -p $PGPORT >/dev/null 2>&1 || wait 30
  pg_isready -h localhost -p $PGPORT >/dev/null 2>&1 || { echo "postgres did not come up" >&2; return 1; }

  PSQL="/opt/homebrew/opt/postgresql@$PGVER/bin/psql"
  # Role/db/extension already exist after the first run, so these are cheap no-ops.
  "$PSQL" -h localhost -p $PGPORT -d postgres -tAc \
    "SELECT 1 FROM pg_roles WHERE rolname='postgres'" | grep -q 1 || \
    "$PSQL" -h localhost -p $PGPORT -d postgres -c \
      "CREATE ROLE postgres WITH LOGIN SUPERUSER PASSWORD 'postgres'" >/dev/null
  "$PSQL" -h localhost -p $PGPORT -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname='$DB'" | grep -q 1 || \
    "$PSQL" -h localhost -p $PGPORT -d postgres -c "CREATE DATABASE $DB OWNER postgres" >/dev/null
  "$PSQL" -h localhost -p $PGPORT -U postgres -d $DB \
    -c "CREATE EXTENSION IF NOT EXISTS vector" >/dev/null

  # The schema lives in migrations and nothing in app/ calls create_all, so
  # skipping this leaves a database that fails on its first query.
  echo "==> migrations"
  $VENV/bin/alembic upgrade head >/dev/null || { echo "migrations failed" >&2; return 1; }

  echo "==> backend on $BACKEND"
  pkill -f "uvicorn app.main:app" 2>/dev/null || true
  free_port 8001 || echo "  (port 8001 still busy, binding anyway)"
  nohup $VENV/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 > /tmp/be.log 2>&1 &
  wait_healthy "$BACKEND/health" 60 /tmp/be.log || return 1
  echo "  up"

  echo "==> frontend on http://localhost:5173"
  pkill -f "vite" 2>/dev/null || true
  free_port 5173 || echo "  (port 5173 still busy, binding anyway)"
  ( cd frontend && nohup npm run dev > /tmp/fe.log 2>&1 & )
  wait_healthy http://localhost:5173 60 /tmp/fe.log || return 1
  echo "  up"
  echo
  echo "  open http://localhost:5173"
}

stop() {
  pkill -f "uvicorn app.main:app" 2>/dev/null || true
  pkill -f "vite" 2>/dev/null || true
  echo "stopped backend + frontend (postgres left running)"
}

case "${1:-start}" in
  start)  start ;;
  stop)   stop ;;
  status) status ;;
  *) echo "usage: $0 [start|stop|status]" >&2; exit 2 ;;
esac
