from fastapi.testclient import TestClient

from main import app
from db.session import get_db_session
from repositories import tenant_repo, user_repo
from services.password_service import hash_password


def _csv_bytes() -> bytes:
    return (
        "资产编号,合同编号,客户姓名,品牌型号,VIN,车牌号,资产所在地,逾期天数,逾期金额,剩余本金,车辆估值,车辆状态,GPS时间\n"
        "A-001,HT-001,张三,宝马3系,LBV000001,苏A12345,江苏省南京市,75,12.5万,180000,150000,未收回,2026-04-20\n"
        ",,, ,,,上海市,abc,foo,,,未知,\n"
    ).encode("utf-8-sig")


def _seed_tenant_user(*, tenant_code: str, email: str, role: str = "operator"):
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_or_create_tenant(
            session, code=tenant_code, name=tenant_code.upper()
        )
        user = user_repo.create_user(
            session,
            email=email,
            password_hash=hash_password("Passw0rd!"),
            role=role,
            display_name=email,
        )
        tenant_repo.create_membership(
            session, user_id=user.id, tenant_id=tenant.id, role=role
        )
        user_repo.set_default_tenant(session, user.id, tenant.id)
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _login(client: TestClient, email: str):
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Passw0rd!"},
    )
    assert response.status_code == 200, response.text


def test_upload_csv_imports_customer_legacy_rows(authed_client):
    response = authed_client.post(
        "/api/data-import/upload",
        data={"source_system": "legacy-loan-core", "import_type": "asset_ledger"},
        files={"file": ("legacy-assets.csv", _csv_bytes(), "text/csv")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    batch = body["batch"]
    assert batch["source_system"] == "legacy-loan-core"
    assert batch["total_rows"] == 2
    assert batch["success_rows"] == 1
    assert batch["error_rows"] == 1
    assert body["detected_columns"]["contract_number"] == "合同编号"

    first = body["rows_preview"][0]
    assert first["row_status"] == "valid"
    assert first["asset_identifier"] == "A-001"
    assert first["province"] == "江苏省"
    assert first["city"] == "南京市"
    assert first["overdue_bucket"] == "M3(61-90天)"
    assert first["overdue_amount"] == 125000
    assert first["recovered_status"] == "未收回"

    second = body["rows_preview"][1]
    assert second["row_status"] == "error"
    assert any(err["field"] == "asset_identifier" for err in second["errors"])

    batches = authed_client.get("/api/data-import/batches")
    assert batches.status_code == 200, batches.text
    assert batches.json()[0]["id"] == batch["id"]

    rows = authed_client.get(f"/api/data-import/batches/{batch['id']}/rows")
    assert rows.status_code == 200, rows.text
    assert rows.json()["batch"]["id"] == batch["id"]
    assert len(rows.json()["rows"]) == 2

    error_rows = authed_client.get(
        f"/api/data-import/batches/{batch['id']}/rows",
        params={"status": "error"},
    )
    assert error_rows.status_code == 200, error_rows.text
    assert len(error_rows.json()["rows"]) == 1


def test_data_import_batch_can_be_edited_and_deleted(authed_client):
    response = authed_client.post(
        "/api/data-import/upload",
        data={"source_system": "legacy-loan-core", "import_type": "asset_ledger"},
        files={"file": ("legacy-assets.csv", _csv_bytes(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    batch_id = response.json()["batch"]["id"]

    updated = authed_client.put(
        f"/api/data-import/batches/{batch_id}",
        json={"filename": "客户退案修正版.csv", "source_system": "人工复核台账"},
    )
    assert updated.status_code == 200, updated.text
    updated_body = updated.json()
    assert updated_body["filename"] == "客户退案修正版.csv"
    assert updated_body["source_system"] == "人工复核台账"

    listed = authed_client.get("/api/data-import/batches")
    assert listed.status_code == 200, listed.text
    listed_batch = next(item for item in listed.json() if item["id"] == batch_id)
    assert listed_batch["filename"] == "客户退案修正版.csv"

    deleted = authed_client.delete(f"/api/data-import/batches/{batch_id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "deleted"

    relisted = authed_client.get("/api/data-import/batches")
    assert relisted.status_code == 200, relisted.text
    assert all(item["id"] != batch_id for item in relisted.json())

    rows = authed_client.get(f"/api/data-import/batches/{batch_id}/rows")
    assert rows.status_code == 404
    assert rows.json()["error"]["code"] == "DATA_IMPORT_BATCH_NOT_FOUND"


def test_data_import_row_can_be_edited_and_recounted(authed_client):
    response = authed_client.post(
        "/api/data-import/upload",
        data={"source_system": "legacy-loan-core", "import_type": "asset_ledger"},
        files={"file": ("legacy-assets.csv", _csv_bytes(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    batch_id = response.json()["batch"]["id"]
    error_row = response.json()["rows_preview"][1]
    assert error_row["row_status"] == "error"

    updated = authed_client.put(
        f"/api/data-import/rows/{error_row['id']}",
        json={
            "debtor_name": "李四",
            "car_description": "奥迪A4L",
            "vin": "LFV000002",
            "province": "上海市",
            "city": "上海市",
            "overdue_days": 45,
            "overdue_amount": 50000,
            "loan_principal": 60000,
            "vehicle_value": 45000,
            "recovered_status": "未收回",
        },
    )
    assert updated.status_code == 200, updated.text
    updated_row = updated.json()
    assert updated_row["row_status"] == "valid"
    assert updated_row["errors"] == []
    assert updated_row["loan_principal"] == 60000

    rows = authed_client.get(f"/api/data-import/batches/{batch_id}/rows")
    assert rows.status_code == 200, rows.text
    assert rows.json()["batch"]["success_rows"] == 2
    assert rows.json()["batch"]["error_rows"] == 0

    overview = authed_client.get("/api/portfolio/overview")
    assert overview.status_code == 200, overview.text
    assert overview.json()["total_asset_count"] == 2
    assert overview.json()["total_ead"] == 240000


def test_data_import_batches_are_tenant_scoped():
    _seed_tenant_user(tenant_code="alpha", email="alpha-import@example.com")
    _seed_tenant_user(tenant_code="beta", email="beta-import@example.com")

    alpha = TestClient(app)
    _login(alpha, "alpha-import@example.com")
    created = alpha.post(
        "/api/data-import/upload",
        data={"source_system": "alpha-core", "import_type": "asset_ledger"},
        files={"file": ("alpha.csv", _csv_bytes(), "text/csv")},
    )
    assert created.status_code == 200, created.text
    batch_id = created.json()["batch"]["id"]

    beta = TestClient(app)
    _login(beta, "beta-import@example.com")
    listed = beta.get("/api/data-import/batches")
    assert listed.status_code == 200, listed.text
    assert listed.json() == []

    foreign = beta.get(f"/api/data-import/batches/{batch_id}/rows")
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "DATA_IMPORT_BATCH_NOT_FOUND"
