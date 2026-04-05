# Backup and Restore

This document covers backup procedures, restore steps, and disaster recovery guidance for Detec server deployments. For server setup, see [SERVER.md](../SERVER.md).

---

## PostgreSQL (production)

### Manual backup

```bash
# Full dump (custom format, compressed)
pg_dump -Fc -h localhost -U detec -d detec -f detec_backup_$(date +%Y%m%d_%H%M%S).dump

# Plain SQL (for inspection or cross-version restore)
pg_dump -h localhost -U detec -d detec > detec_backup_$(date +%Y%m%d_%H%M%S).sql
```

### Scheduled backup (cron)

Add to the server's crontab (`crontab -e`):

```cron
# Daily backup at 02:00, keep 14 days
0 2 * * * pg_dump -Fc -h localhost -U detec -d detec -f /var/backups/detec/detec_$(date +\%Y\%m\%d).dump && find /var/backups/detec -name "detec_*.dump" -mtime +14 -delete
```

Create the backup directory first:

```bash
mkdir -p /var/backups/detec
```

### Docker volume backup

When running via `docker-compose.prod.yml`, PostgreSQL data lives in the `pgdata` Docker volume:

```bash
# Stop writes (optional but recommended for consistency)
docker compose -f docker-compose.prod.yml exec db pg_dump -U detec -Fc detec > detec_backup.dump

# Or dump the raw volume (cold backup — requires stopping the container)
docker compose -f docker-compose.prod.yml stop db
docker run --rm -v detec_pgdata:/data -v $(pwd):/backup alpine tar czf /backup/pgdata_backup.tar.gz -C /data .
docker compose -f docker-compose.prod.yml start db
```

### Restore

```bash
# Drop and recreate the database
dropdb -h localhost -U detec detec
createdb -h localhost -U detec detec

# Restore from custom-format dump
pg_restore -h localhost -U detec -d detec detec_backup.dump

# Restart the API (runs Alembic migrations automatically to reconcile schema)
# Docker:
docker compose -f docker-compose.prod.yml restart api
# Bare metal:
systemctl restart detec-server
```

**Alembic compatibility:** The API runs `alembic upgrade head` on startup. If the backup is from an older schema version, migrations apply automatically. If restoring from a newer version than the current code, update the code first.

---

## SQLite (evaluation / development)

SQLite uses WAL (Write-Ahead Logging) mode. For a consistent backup:

```bash
# Checkpoint the WAL to ensure all data is in the main DB file
sqlite3 /path/to/detec.db "PRAGMA wal_checkpoint(TRUNCATE);"

# Copy the database file
cp /path/to/detec.db /var/backups/detec/detec_$(date +%Y%m%d).db
```

Default database locations:
- **macOS:** `~/Library/Application Support/Detec/detec.db`
- **Windows:** `C:\ProgramData\Detec\detec.db`
- **Linux:** `~/.local/share/detec/detec.db`

### Restore

```bash
# Stop the API
systemctl stop detec-server  # or Ctrl+C

# Replace the database file
cp /var/backups/detec/detec_YYYYMMDD.db /path/to/detec.db

# Restart the API
systemctl start detec-server
```

---

## Backup verification

Periodically verify that backups are restorable. Restore to a test instance:

```bash
# Create a throwaway database
createdb -h localhost -U detec detec_test_restore
pg_restore -h localhost -U detec -d detec_test_restore detec_backup.dump

# Verify row counts
psql -h localhost -U detec -d detec_test_restore -c "SELECT 'events', count(*) FROM events UNION ALL SELECT 'policies', count(*) FROM policies UNION ALL SELECT 'endpoints', count(*) FROM endpoints;"

# Clean up
dropdb -h localhost -U detec detec_test_restore
```

---

## Retention guidance

| Deployment size | Backup frequency | Retention |
|-----------------|-----------------|-----------|
| Evaluation (<50 endpoints) | Weekly | 4 weeks |
| Production (50-500 endpoints) | Daily | 30 days |
| Enterprise (>500 endpoints) | Daily + WAL archiving | 90 days + point-in-time recovery |

For enterprise deployments requiring point-in-time recovery, configure PostgreSQL WAL archiving (`archive_mode = on`, `archive_command`). This is beyond the scope of this document — refer to the [PostgreSQL documentation](https://www.postgresql.org/docs/current/continuous-archiving.html).

---

## Disaster recovery

### Full server loss

1. Provision a new server with the same OS and PostgreSQL version.
2. Restore the database from the most recent backup (see Restore above).
3. Set the same environment variables (`JWT_SECRET`, `SEED_ADMIN_PASSWORD`, `ALLOWED_ORIGINS`, etc.). **Use the same `JWT_SECRET`** — changing it invalidates all existing JWT tokens and agent API keys.
4. Start the API. Alembic migrations reconcile schema automatically.
5. Agents will reconnect on their next heartbeat interval (default 300s).

### Corrupted database

If the database is corrupted but the server is still running:

```bash
# Stop the API immediately to prevent further writes
systemctl stop detec-server

# Restore from the most recent backup
pg_restore -h localhost -U detec -d detec --clean detec_backup.dump

# Restart the API
systemctl start detec-server
```

### Off-site backup

For production deployments, copy backups to a remote location:

```bash
# Example: rsync to a backup server
rsync -az /var/backups/detec/ backup-server:/backups/detec/

# Example: upload to S3
aws s3 sync /var/backups/detec/ s3://your-bucket/detec-backups/
```

---

*Related: [SERVER.md](../SERVER.md) (deployment), [docs/rollback.md](rollback.md) (playbook rollback)*
