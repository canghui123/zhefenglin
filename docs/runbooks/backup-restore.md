# Backup & Restore Runbook

## PostgreSQL Backup

### Automated Daily Backup

Run `scripts/backup_postgres.sh` via cron:

```cron
0 2 * * * /path/to/scripts/backup_postgres.sh
```

### Manual Backup

```bash
export PGHOST=localhost PGPORT=5432 PGUSER=app PGDATABASE=auto_finance
pg_dump --format=custom --file="backup_$(date +%Y%m%d_%H%M%S).dump"
```

### Restore

```bash
# Restore to a clean database
createdb auto_finance_restore
pg_restore --dbname=auto_finance_restore backup_20260413.dump

# Or restore in-place (destructive)
pg_restore --clean --dbname=auto_finance backup_20260413.dump
```

### Verify Backup Integrity

```bash
pg_restore --list backup_20260413.dump | head -20
```

## Object Storage Backup

### Automated Sync

Run `scripts/backup_storage.sh` via cron:

```cron
30 2 * * * /path/to/scripts/backup_storage.sh
```

### Manual Sync (MinIO/S3)

```bash
# Using mc (MinIO Client)
mc mirror minio/auto-finance backup/auto-finance-$(date +%Y%m%d)

# Using aws cli
aws s3 sync s3://auto-finance s3://auto-finance-backup/$(date +%Y%m%d)
```

## Disaster Recovery Procedure

1. **Assess**: Determine scope (database, storage, or both)
2. **Provision**: Create a clean database instance
3. **Restore DB**: `pg_restore` from the latest daily backup
4. **Restore Storage**: Sync backup bucket to production bucket
5. **Run Migrations**: `cd backend && alembic upgrade head`
6. **Verify**: Run smoke tests against the restored instance
7. **Switchover**: Update DNS/load balancer to point to restored instance

## Recovery Time Objectives

| Component | RPO (max data loss) | RTO (max downtime) |
|-----------|--------------------|--------------------|
| Database | 24 hours | 1 hour |
| Object storage | 24 hours | 2 hours |
| Full system | 24 hours | 3 hours |
