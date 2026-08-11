#!/bin/bash
# Cleanly stop Postgres and detach the Seagate image so the drive can be ejected.
PG=/usr/local/opt/postgresql@17/bin
$PG/pg_ctl -D /Volumes/CivicLedgerData/pgdata stop 2>/dev/null && echo "postgres stopped"
hdiutil detach /Volumes/CivicLedgerData 2>/dev/null && echo "image detached — safe to eject the Seagate"
