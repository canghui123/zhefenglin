# Data Retention Policy

## Retention Periods

| Data Type | Retention | Purge Method |
|-----------|-----------|--------------|
| Asset packages (Excel) | 2 years from upload | Delete from object storage + DB record |
| Valuation cache | 7 days (auto-refresh) | Overwritten on next query |
| Simulation results | 1 year from creation | Soft-delete + archive |
| Generated reports | 1 year from generation | Delete from object storage |
| Audit logs | 3 years (regulatory) | Archive to cold storage after 1 year |
| User sessions | 24 hours (JWT expiry) | Auto-expired, no cleanup needed |
| Job runs | 90 days | Delete completed jobs older than 90 days |
| Depreciation cache | 30 days | Overwritten on next prediction |

## Automated Cleanup

Scheduled purge jobs (to be implemented):
1. `purge_old_jobs` — Delete job_runs where `finished_at < now() - 90 days`
2. `purge_valuation_cache` — Already handled by 7-day freshness check in query
3. `archive_audit_logs` — Move audit_logs older than 1 year to archive table

## Backup Requirements

- **Database**: Daily full backup, retained for 30 days
- **Object storage**: Daily incremental sync to backup bucket
- **Audit logs**: Separate backup stream, retained for 3 years

## Right to Deletion

When a tenant requests data deletion:
1. Delete all asset_packages, sandbox_results, job_runs for the tenant
2. Delete all files in object storage with tenant-prefixed keys
3. Anonymize (but do not delete) audit_logs for regulatory compliance
4. Deactivate user accounts and memberships
5. Document the deletion in a separate compliance log
