#!/usr/bin/env bash
# Daily PostgreSQL backup script.
# Schedule via cron: 0 2 * * * /path/to/scripts/backup_postgres.sh
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/auto-finance/postgres}"
RETAIN_DAYS="${RETAIN_DAYS:-30}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-app}"
PGDATABASE="${PGDATABASE:-auto_finance}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${PGDATABASE}_${TIMESTAMP}.dump"

echo "[$(date)] Starting PostgreSQL backup → $BACKUP_FILE"
pg_dump \
  --host="$PGHOST" \
  --port="$PGPORT" \
  --username="$PGUSER" \
  --format=custom \
  --file="$BACKUP_FILE" \
  "$PGDATABASE"

echo "[$(date)] Backup complete: $(du -h "$BACKUP_FILE" | cut -f1)"

# Purge old backups
echo "[$(date)] Purging backups older than $RETAIN_DAYS days"
find "$BACKUP_DIR" -name "*.dump" -mtime "+$RETAIN_DAYS" -delete

echo "[$(date)] Done."
