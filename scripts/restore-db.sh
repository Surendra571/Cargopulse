#!/usr/bin/env bash
set -euo pipefail

# CargoPulse PostgreSQL Restore Script
# Usage: ./scripts/restore-db.sh <backup_file.dump>

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <path-to-backup.dump>"
  exit 1
fi

BACKUP_FILE="$1"
if [[ ! -f "${BACKUP_FILE}" ]]; then
  echo "Error: Backup file not found: ${BACKUP_FILE}"
  exit 1
fi

echo "WARNING: Restoring '${BACKUP_FILE}' will overwrite existing database objects."
if [[ "${CONFIRM_RESTORE:-}" != "YES" ]]; then
  read -r -p "Type YES to continue: " REPLY
  if [[ "${REPLY}" != "YES" ]]; then
    echo "Restore aborted."
    exit 1
  fi
fi

echo "[$(date -u +%FT%TZ)] Starting PostgreSQL restore from ${BACKUP_FILE}..."

if [[ -n "${DATABASE_SYNC_URL:-}" ]]; then
  PG_URI="${DATABASE_SYNC_URL/postgresql+psycopg2:\/\//postgresql://}"
  pg_restore --dbname="${PG_URI}" --clean --if-exists --no-owner --no-acl "${BACKUP_FILE}"
else
  pg_restore --clean --if-exists --no-owner --no-acl -d "${PGDATABASE:-cargopulse}" "${BACKUP_FILE}"
fi

echo "[$(date -u +%FT%TZ)] Restore complete. Running Alembic verification..."
(cd backend && alembic current)
