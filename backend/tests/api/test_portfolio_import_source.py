from fastapi.testclient import TestClient

from db.session import get_db_session
from main import app
from repositories import tenant_repo, user_repo
from services.password_service import hash_password


def _portfolio_csv() -> bytes:
    return (
        "资产编号,合同编号,客户姓名,品牌型号,VIN,车牌号,资产所在地,逾期天数,逾期金额,剩余本金,车辆估值,车辆状态,GPS时间\n"
        "IMP-001,HT-001,张三,宝马3系,LBV000001,苏A12345,江苏省南京市,75,12万,180000,150000,未收回,2026-04-20\n"
        "IMP-002,HT-002,李四,奥迪A4L,LFV000002,浙A54321,浙江省杭州市,110,8万,120000,130000,已入库,2026-04-18\n"
    ).encode("utf-8-sig")


def _seed_user(email: str, *, role: str = "operator"):
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_or_create_tenant(
            session, code="default", name="DEFAULT"
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


def _client(email: str, *, role: str = "operator") -> TestClient:
    _seed_user(email, role=role)
    client = TestClient(app)
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Passw0rd!"},
    )
    assert response.status_code == 200, response.text
    return client


def _upload_import(client: TestClient) -> dict:
    response = client.post(
        "/api/data-import/upload",
        data={"source_system": "customer-core", "import_type": "asset_ledger"},
        files={"file": ("customer-portfolio.csv", _portfolio_csv(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    return response.json()["batch"]


def test_portfolio_pages_use_latest_customer_import(authed_client):
    batch = _upload_import(authed_client)

    overview = authed_client.get("/api/portfolio/overview")
    assert overview.status_code == 200, overview.text
    overview_body = overview.json()
    assert overview_body["data_source"] == "customer_import"
    assert overview_body["source_batch_id"] == batch["id"]
    assert overview_body["source_filename"] == "customer-portfolio.csv"
    assert overview_body["total_asset_count"] == 2
    assert overview_body["total_ead"] == 300000

    segmentation = authed_client.get(
        "/api/portfolio/segmentation",
        params={"dimension": "recovered_status"},
    )
    assert segmentation.status_code == 200, segmentation.text
    groups = {item["dimension_value"]: item for item in segmentation.json()["groups"]}
    assert groups["未收回"]["asset_count"] == 1
    assert groups["未收回"]["total_ead"] == 180000
    assert groups["已入库"]["asset_count"] == 1
    assert groups["已入库"]["total_ead"] == 120000

    strategies = authed_client.get("/api/portfolio/strategies", params={"segment_index": 0})
    assert strategies.status_code == 200, strategies.text
    strategy_body = strategies.json()
    assert strategy_body["segment_name"] == "M3(61-90天) | 未收回"
    assert strategy_body["segment_count"] == 1
    assert strategy_body["segment_ead"] == 180000

    cashflow = authed_client.get("/api/portfolio/cashflow")
    assert cashflow.status_code == 200, cashflow.text
    cashflow_body = cashflow.json()
    assert cashflow_body["total_ead"] == 300000
    assert {item["segment_name"] for item in cashflow_body["by_segment"]} == {
        "M3(61-90天) | 未收回",
        "M4(91-120天) | 已入库",
    }

    action_center = authed_client.get("/api/portfolio/action-center")
    assert action_center.status_code == 200, action_center.text
    action_body = action_center.json()
    assert action_body["recovery_tasks"][0]["segment_name"] == "M3(61-90天) | 未收回"
    assert action_body["recovery_tasks"][0]["count"] == 1
    assert action_body["auction_ready"][0]["segment_name"] == "M4(91-120天) | 已入库"
    assert action_body["auction_ready"][0]["count"] == 1

    candidates = authed_client.get(
        "/api/portfolio/action-center/candidates",
        params={
            "order_type": "towing",
            "segment_name": "M3(61-90天) | 未收回",
        },
    )
    assert candidates.status_code == 200, candidates.text
    candidate = candidates.json()["candidates"][0]
    assert candidate["asset_identifier"] == "IMP-001"
    assert candidate["debtor_name"] == "张三"
    assert candidate["car_description"] == "宝马3系"
    assert candidate["vehicle_value"] == 150000


def test_management_decision_pages_use_imported_portfolio():
    client = _client("manager-import@example.com", role="manager")
    _upload_import(client)

    executive = client.get("/api/portfolio/executive")
    assert executive.status_code == 200, executive.text
    assert executive.json()["overview"]["data_source"] == "customer_import"
    assert executive.json()["overview"]["total_asset_count"] == 2

    manager = client.get("/api/portfolio/manager-playbook")
    assert manager.status_code == 200, manager.text
    assert manager.json()["kpis"][0]["recommended_value"] > 0

    supervisor = client.get("/api/portfolio/supervisor-console")
    assert supervisor.status_code == 200, supervisor.text
    pool_segments = {item["segment_name"] for item in supervisor.json()["high_priority_pool"]}
    assert "M3(61-90天) | 未收回" in pool_segments
    assert "M4(91-120天) | 已入库" in pool_segments


def test_clear_portfolio_source_preserves_import_history(authed_client):
    old_batch = _upload_import(authed_client)

    cleared = authed_client.post("/api/portfolio/source/clear")
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["cleared_batches"] == 1

    overview = authed_client.get("/api/portfolio/overview")
    assert overview.status_code == 200, overview.text
    overview_body = overview.json()
    assert overview_body["data_source"] == "empty"
    assert overview_body["total_asset_count"] == 0
    assert overview_body["total_ead"] == 0

    rows = authed_client.get(f"/api/data-import/batches/{old_batch['id']}/rows")
    assert rows.status_code == 200, rows.text
    assert rows.json()["batch"]["status"] == "archived"
    assert len(rows.json()["rows"]) == 2

    new_batch = _upload_import(authed_client)
    assert new_batch["id"] != old_batch["id"]

    refreshed = authed_client.get("/api/portfolio/overview")
    assert refreshed.status_code == 200, refreshed.text
    refreshed_body = refreshed.json()
    assert refreshed_body["data_source"] == "customer_import"
    assert refreshed_body["source_batch_id"] == new_batch["id"]
    assert refreshed_body["total_asset_count"] == 2

    batches = authed_client.get("/api/data-import/batches")
    assert batches.status_code == 200, batches.text
    statuses = {item["id"]: item["status"] for item in batches.json()}
    assert statuses[new_batch["id"]] == "parsed"
    assert statuses[old_batch["id"]] == "archived"
