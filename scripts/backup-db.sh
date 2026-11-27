#!/usr/bin/env bash
set -euo pipefail

# CargoPulse PostgreSQL Automated Backup Script
# Usage: ./scripts/backup-db.sh [output_dir]
# Requires: DATABASE_SYNC_URL or PGHOST/PGPORT/PGUSER/PGDATABASE/PGPASSWORD

BACKUP_DIR="${1:-./backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${BACKUP_DIR}/cargopulse_${TIMESTAMP}.dump"

mkdir -p "${BACKUP_DIR}"

echo "[$(date -u +%FT%TZ)] Starting PostgreSQL backup -> ${BACKUP_FILE}"

if [[ -n "${DATABASE_SYNC_URL:-}" ]]; then
  # Convert SQLAlchemy driver prefix if present
  PG_URI="${DATABASE_SYNC_URL/postgresql+psycopg2:\/\//postgresql://}"
  pg_dump "${PG_URI}" --format=custom --compress=9 --no-owner --no-acl --file="${BACKUP_FILE}"
else
  pg_dump --format=custom --compress=9 --no-owner --no-acl --file="${BACKUP_FILE}"
fi

echo "[$(date -u +%FT%TZ)] Backup complete ($(du -h "${BACKUP_FILE}" | cut -f1))"

if [[ -n "${S3_BACKUP_BUCKET:-}" ]]; then
  echo "[$(date -u +%FT%TZ)] Uploading backup to s3://${S3_BACKUP_BUCKET}/postgres/"
  aws s3 cp "${BACKUP_FILE}" "s3://${S3_BACKUP_BUCKET}/postgres/$(basename "${BACKUP_FILE}")" --sse AES256
fi

# Prune backups older than retention window
find "${BACKUP_DIR}" -name "cargopulse_*.dump" -type f -mtime +"${RETENTION_DAYS}" -delete
echo "[$(date -u +%FT%TZ)] Retention cleanup complete (kept last ${RETENTION_DAYS} days)."
