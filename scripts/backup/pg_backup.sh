#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# pg_backup.sh — PostgreSQL backup wrapper for Agentic Governance
#
# Creates a timestamped, gzip-compressed pg_dump and prunes backups older
# than 7 days.
#
# Usage:
#   DATABASE_URL="postgresql://user:pass@host:5432/dbname" ./pg_backup.sh
#
# Cron example (daily at 02:00, logs to /var/log/pg_backup.log):
#   0 2 * * * DATABASE_URL="postgresql://user:pass@host:5432/dbname" \
#             /path/to/scripts/backup/pg_backup.sh >> /var/log/pg_backup.log 2>&1
#
# Environment variables:
#   DATABASE_URL   — full PostgreSQL connection string
#                    (default: postgresql://localhost:5432/detec)
#   BACKUP_DIR     — directory to store backups (default: script directory)
#   RETENTION_DAYS — number of daily backups to keep (default: 7)
# ---------------------------------------------------------------------------
set -euo pipefail

DATABASE_URL="${DATABASE_URL:-postgresql://localhost:5432/detec}"
BACKUP_DIR="${BACKUP_DIR:-$(cd "$(dirname "$0")" && pwd)}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.sql.gz"

echo "=== pg_backup.sh — $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "Database : ${DATABASE_URL%%@*}@***"
echo "Backup   : ${BACKUP_FILE}"

# --- Run the dump --------------------------------------------------------
pg_dump "${DATABASE_URL}" | gzip > "${BACKUP_FILE}"

FILESIZE=$(ls -lh "${BACKUP_FILE}" | awk '{print $5}')
echo "Complete : ${BACKUP_FILE} (${FILESIZE})"

# --- Prune old backups ---------------------------------------------------
DELETED=0
find "${BACKUP_DIR}" -maxdepth 1 -name "backup_*.sql.gz" -type f -mtime +${RETENTION_DAYS} -print -delete | while read -r f; do
    echo "Pruned   : ${f}"
    DELETED=$((DELETED + 1))
done
echo "Retention: keeping last ${RETENTION_DAYS} days"
echo "=== Done ==="
