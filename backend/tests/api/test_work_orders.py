from fastapi.testclient import TestClient

from main import app
from db.session import get_db_session
from repositories import tenant_repo, user_repo
from services.password_service import hash_password


def _create_payload(**overrides):
    payload = {
        "order_type": "towing",
        "title": "委外拖车：M4未收回",
        "target_description": "20台未收回车辆",
        "priority": "high",
        "source_type": "portfolio_segment",
        "source_id": "M4(91-120天) | 未收回",
        "payload": {"count": 20, "total_ead": 2_000_000},
    }
    payload.update(overrides)
    return payload


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


def test_operator_can_create_list_and_complete_work_order(authed_client):
    created = authed_client.post("/api/work-orders", json=_create_payload())

    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "pending"
    assert body["order_type"] == "towing"
    assert body["payload"]["count"] == 20

    listed = authed_client.get("/api/work-orders")
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == body["id"] for item in listed.json())

    started = authed_client.put(
        f"/api/work-orders/{body['id']}/status",
        json={"status": "in_progress"},
    )
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "in_progress"

    completed = authed_client.put(
        f"/api/work-orders/{body['id']}/status",
        json={"status": "completed", "result": {"vendor": "mock-towing"}},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["result"]["vendor"] == "mock-towing"


def test_action_center_returns_asset_level_towing_candidates(authed_client):
    response = authed_client.get(
        "/api/portfolio/action-center/candidates",
        params={
            "order_type": "towing",
            "segment_name": "M3(61-90天) | 未收回",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["order_type"] == "towing"
    assert body["segment_name"] == "M3(61-90天) | 未收回"
    assert body["segment_count"] == len(body["candidates"])
    assert body["segment_count"] > 0
    first = body["candidates"][0]
    assert first["asset_identifier"]
    assert first["overdue_bucket"] == "M3(61-90天)"
    assert first["recovered_status"] == "未收回"
    assert first["default_towing_commission"] > 0
    assert first["default_work_order_days"] > 0


def test_batch_work_order_payload_can_store_asset_line_items(authed_client):
    candidates = authed_client.get(
        "/api/portfolio/action-center/candidates",
        params={
            "order_type": "auction_push",
            "segment_name": "M3(61-90天) | 已入库",
        },
    )
    assert candidates.status_code == 200, candidates.text
    selected = candidates.json()["candidates"][:2]

    created = authed_client.post(
        "/api/work-orders",
        json=_create_payload(
            order_type="auction_push",
            title="拍卖推送：M3在库批量",
            source_id="M3(61-90天) | 已入库",
            payload={
                "workflow": "auction_batch_builder",
                "line_items": [
                    {
                        "asset_identifier": item["asset_identifier"],
                        "starting_price": item["default_starting_price"],
                        "auction_start_at": item["default_auction_start_at"],
                        "auction_end_at": item["default_auction_end_at"],
                    }
                    for item in selected
                ],
            },
        ),
    )

    assert created.status_code == 200, created.text
    body = created.json()
    assert body["order_type"] == "auction_push"
    assert body["payload"]["workflow"] == "auction_batch_builder"
    assert len(body["payload"]["line_items"]) == 2


def test_invalid_work_order_transition_is_rejected(authed_client):
    created = authed_client.post("/api/work-orders", json=_create_payload())
    work_order_id = created.json()["id"]

    completed = authed_client.put(
        f"/api/work-orders/{work_order_id}/status",
        json={"status": "completed"},
    )
    assert completed.status_code == 200, completed.text

    reopened = authed_client.put(
        f"/api/work-orders/{work_order_id}/status",
        json={"status": "in_progress"},
    )
    assert reopened.status_code == 400
    assert reopened.json()["error"]["code"] == "INVALID_WORK_ORDER_TRANSITION"


def test_work_orders_are_tenant_scoped():
    _seed_tenant_user(tenant_code="alpha", email="alpha-work@example.com")
    _seed_tenant_user(tenant_code="beta", email="beta-work@example.com")

    alpha = TestClient(app)
    _login(alpha, "alpha-work@example.com")
    created = alpha.post("/api/work-orders", json=_create_payload())
    assert created.status_code == 200, created.text
    work_order_id = created.json()["id"]

    beta = TestClient(app)
    _login(beta, "beta-work@example.com")
    foreign = beta.get(f"/api/work-orders/{work_order_id}")
    assert foreign.status_code == 404

    listed = beta.get("/api/work-orders")
    assert listed.status_code == 200
    assert all(row["id"] != work_order_id for row in listed.json())
