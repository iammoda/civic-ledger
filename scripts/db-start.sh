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
echo "Database up: postgres on :5432 (data on Seagate), redis on :6379"
