#!/bin/bash
# Nightly backup of the Civic Ledger database.
#
# Dumps the Postgres DB (custom format, compressed) to a local backups dir
# OFF the Seagate drive, keeps the last N dumps, and optionally syncs to a
# remote via rclone if BACKUP_RCLONE_REMOTE is set (e.g. "b2:civic-ledger-backups").
#
# Usage:
#   scripts/db-backup.sh                  # one-off backup
#   BACKUP_RCLONE_REMOTE=b2:bucket scripts/db-backup.sh
#
# Install as a nightly job (macOS):
#   crontab -e
#   15 3 * * * /Users/<you>/path/to/repo/scripts/db-backup.sh >> ~/civic-backup.log 2>&1
#
# Restore:
#   createdb civic_platform
#   pg_restore -d civic_platform --no-owner backups/civic_platform_<stamp>.dump
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PG_BIN="${PG_BIN:-/usr/local/opt/postgresql@17/bin}"
[ -x "$PG_BIN/pg_dump" ] || PG_BIN="$(dirname "$(command -v pg_dump)")"

# Backups live on the internal disk, NOT the Seagate drive the DB runs from.
BACKUP_DIR="${BACKUP_DIR:-$HOME/civic-ledger-backups}"
KEEP="${BACKUP_KEEP:-14}"
DB_NAME="${DB_NAME:-civic_platform}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/${DB_NAME}_${STAMP}.dump"

"$PG_BIN/pg_dump" --format=custom --compress=9 --no-owner \
  --dbname="$DB_NAME" --file="$OUT"

SIZE="$(du -h "$OUT" | cut -f1)"
echo "$(date '+%F %T') backup ok: $OUT ($SIZE)"

# Also snapshot the raw imports dir (lobby ZIPs etc. — hard to re-fetch past
# Cloudflare), but only files newer than the last archive run.
IMPORTS_DIR="${IMPORTS_DIR:-/Volumes/CivicLedgerData/imports}"
if [ -d "$IMPORTS_DIR" ]; then
  rsync -a --ignore-existing "$IMPORTS_DIR/" "$BACKUP_DIR/imports/" 2>/dev/null || true
fi

# Rotate: keep the newest $KEEP dumps.
ls -1t "$BACKUP_DIR"/${DB_NAME}_*.dump 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f "$old"
  echo "rotated out: $old"
done

# Optional offsite sync.
if [ -n "${BACKUP_RCLONE_REMOTE:-}" ] && command -v rclone >/dev/null 2>&1; then
  rclone sync "$BACKUP_DIR" "$BACKUP_RCLONE_REMOTE" --exclude ".DS_Store"
  echo "$(date '+%F %T') offsite sync ok: $BACKUP_RCLONE_REMOTE"
fi
