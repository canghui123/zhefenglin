#!/usr/bin/env bash
# Daily object storage backup script.
# Syncs the primary bucket to a backup bucket / local directory.
# Schedule via cron: 30 2 * * * /path/to/scripts/backup_storage.sh
set -euo pipefail

SOURCE_BUCKET="${S3_BUCKET:-auto-finance}"
BACKUP_BUCKET="${BACKUP_BUCKET:-auto-finance-backup}"
S3_ENDPOINT="${S3_ENDPOINT:-http://localhost:9000}"
TIMESTAMP=$(date +%Y%m%d)

echo "[$(date)] Starting storage backup: $SOURCE_BUCKET → $BACKUP_BUCKET/$TIMESTAMP"

# Using mc (MinIO Client) — install: https://min.io/docs/minio/linux/reference/minio-mc.html
if command -v mc &>/dev/null; then
  mc alias set src "$S3_ENDPOINT" "${S3_ACCESS_KEY:-}" "${S3_SECRET_KEY:-}" 2>/dev/null || true
  mc mirror --overwrite "src/$SOURCE_BUCKET" "src/$BACKUP_BUCKET/$TIMESTAMP"
  echo "[$(date)] Backup complete via mc"
elif command -v aws &>/dev/null; then
  aws --endpoint-url "$S3_ENDPOINT" s3 sync \
    "s3://$SOURCE_BUCKET" "s3://$BACKUP_BUCKET/$TIMESTAMP"
  echo "[$(date)] Backup complete via aws cli"
else
  echo "[$(date)] ERROR: Neither mc nor aws CLI found. Install one to enable storage backup."
  exit 1
fi

echo "[$(date)] Done."
