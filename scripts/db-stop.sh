#!/bin/bash
# Cleanly stop the worker and Postgres, then detach the Seagate image.
PG=/usr/local/opt/postgresql@17/bin
pkill -f "arq app.workers.main.WorkerSettings" 2>/dev/null && echo "worker stopped"
$PG/pg_ctl -D /Volumes/CivicLedgerData/pgdata stop 2>/dev/null && echo "postgres stopped"
hdiutil detach /Volumes/CivicLedgerData 2>/dev/null && echo "image detached — safe to eject the Seagate"
