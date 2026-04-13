# Tenant Onboarding Runbook

## Prerequisites

- Admin user credentials
- Tenant organization name and code
- Initial user email addresses and roles

## Steps

### 1. Create Tenant

```bash
cd backend
python3 -c "
from db.session import get_db_session
from repositories import tenant_repo

gen = get_db_session()
session = next(gen)
tenant = tenant_repo.get_or_create_tenant(session, code='NEW_CODE', name='Organization Name')
session.commit()
print(f'Tenant created: id={tenant.id}, code={tenant.code}')
"
```

### 2. Create Admin User for Tenant

```bash
python3 scripts/create_admin.py \
  --email admin@neworg.com \
  --password 'SecurePassword123!' \
  --role admin \
  --tenant-code NEW_CODE
```

### 3. Create Additional Users

Repeat for each user with appropriate roles:
- `admin` — Full access, user management
- `manager` — Portfolio management, strategy approval
- `operator` — Asset uploads, calculations, simulations
- `viewer` — Read-only access to results

### 4. Verify Access

```bash
curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@neworg.com","password":"SecurePassword123!"}' \
  -c cookies.txt

curl -s http://localhost:8000/api/asset-package/list/all -b cookies.txt
# Should return empty array for new tenant
```

### 5. Tenant Isolation Verification

Confirm the new tenant cannot see data from other tenants:
- Upload a test asset package as the new tenant
- Verify it is NOT visible when logged in as a different tenant
- Verify audit log entries are created with the correct tenant_id

## Decommissioning

See [data-retention.md](../security/data-retention.md) for the Right to Deletion procedure.
