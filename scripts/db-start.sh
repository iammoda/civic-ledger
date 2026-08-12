#!/bin/bash
# Start the Civic Ledger database (Postgres data lives on the Seagate drive).
set -e
BUNDLE="/Volumes/Seagate Backup Plus Drive/civic-ledger.sparsebundle"
PG=/usr/local/opt/postgresql@17/bin

if [ ! -d "/Volumes/CivicLedgerData" ]; then
  if [ ! -d "$BUNDLE" ]; then
    echo "ERROR: Seagate drive not connected (or image missing). Plug it in first." >&2
    exit 1
  fi
  hdiutil attach "$BUNDLE"
fi

if ! $PG/pg_ctl -D /Volumes/CivicLedgerData/pgdata status >/dev/null 2>&1; then
  $PG/pg_ctl -D /Volumes/CivicLedgerData/pgdata -l /Volumes/CivicLedgerData/postgres.log start
fi
redis-cli ping >/dev/null 2>&1 || redis-server --daemonize yes --dir /tmp

# Background worker: 30-min data syncs, daily petitions, weekly expenses/
# influence, nightly stats + detectors, hourly notifications. This is what
# keeps the data fresh — without it the site is a frozen snapshot.
REPO="$(cd "$(dirname "$0")/.." && pwd)"
if ! pgrep -f "arq app.workers.main.WorkerSettings" >/dev/null 2>&1; then
  (cd "$REPO" && PYTHONPATH=backend nohup .venv/bin/python -m arq app.workers.main.WorkerSettings \
    > /tmp/civic_worker.log 2>&1 &)
  echo "worker started (log: /tmp/civic_worker.log)"
fi
echo "Database up: postgres on :5432 (data on Seagate), redis on :6379"
