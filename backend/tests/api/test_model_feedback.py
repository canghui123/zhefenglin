from fastapi.testclient import TestClient

from db.session import get_db_session
from main import app
from repositories import tenant_repo, user_repo
from services.password_service import hash_password


def _seed_user(*, email: str, role: str, tenant_code: str = "model-feedback"):
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_or_create_tenant(
            session,
            code=tenant_code,
            name=tenant_code.upper(),
        )
        user = user_repo.create_user(
            session,
            email=email,
            password_hash=hash_password("Passw0rd!"),
            role=role,
            display_name=email,
        )
        tenant_repo.create_membership(
            session,
            user_id=user.id,
            tenant_id=tenant.id,
            role=role,
        )
        user_repo.set_default_tenant(session, user.id, tenant.id)
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _login(email: str) -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Passw0rd!"},
    )
    assert response.status_code == 200, response.text
    return client


def _outcome_payload(**overrides):
    payload = {
        "asset_identifier": "VIN-001",
        "strategy_path": "auction",
        "province": "江苏省",
        "city": "南京市",
        "predicted_recovery_amount": 100000,
        "actual_recovery_amount": 85000,
        "predicted_cycle_days": 30,
        "actual_cycle_days": 45,
        "predicted_success_probability": 0.75,
        "outcome_status": "partial",
    }
    payload.update(overrides)
    return payload


def test_operator_can_record_and_read_feedback_outcomes(authed_client):
    created = authed_client.post(
        "/api/model-feedback/outcomes",
        json=_outcome_payload(),
    )

    assert created.status_code == 200, created.text
    assert created.json()["asset_identifier"] == "VIN-001"

    listed = authed_client.get("/api/model-feedback/outcomes")
    assert listed.status_code == 200, listed.text
    assert any(row["asset_identifier"] == "VIN-001" for row in listed.json())

    summary = authed_client.get("/api/model-feedback/summary")
    assert summary.status_code == 200, summary.text
    assert summary.json()["sample_count"] == 1


def test_manager_can_create_learning_run_but_operator_cannot(authed_client):
    created = authed_client.post(
        "/api/model-feedback/outcomes",
        json=_outcome_payload(),
    )
    assert created.status_code == 200, created.text

    rejected = authed_client.post(
        "/api/model-feedback/learning-runs",
        json={"apply_region_adjustments": False},
    )
    assert rejected.status_code == 403

    _seed_user(email="model-manager@example.com", role="manager")
    manager = _login("model-manager@example.com")
    manager.post("/api/model-feedback/outcomes", json=_outcome_payload(asset_identifier="VIN-002"))

    run = manager.post(
        "/api/model-feedback/learning-runs",
        json={"apply_region_adjustments": False},
    )
    assert run.status_code == 200, run.text
    assert run.json()["sample_count"] == 1
    assert run.json()["applied"] is False


def test_manager_can_import_feedback_spreadsheet_and_trigger_learning():
    _seed_user(
        email="feedback-import-manager@example.com",
        role="manager",
        tenant_code="feedback-import",
    )
    manager = _login("feedback-import-manager@example.com")
    csv = "\n".join(
        [
            "资产标识,实际路径,省份,城市,预测回款,实际回款,预测周期,实际周期,预测成功率,实际结果,复盘备注",
            "CAR-001,拍卖,江苏省,南京市,100000,90000,30,45,75%,部分成功,实际拖期",
            "CAR-002,拖车,江苏省,苏州市,80000,85000,60,50,0.60,成功,找车顺利",
            ",拍卖,江苏省,南京市,100000,90000,30,45,75%,失败,缺少资产",
        ]
    )

    response = manager.post(
        "/api/model-feedback/outcomes/import",
        files={"file": ("feedback.csv", csv.encode("utf-8-sig"), "text/csv")},
        data={"apply_success_adjustment": "true"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_rows"] == 3
    assert data["imported_rows"] == 2
    assert data["error_rows"] == 1
    assert data["errors"][0]["row_number"] == 4
    assert data["learning_run"]["sample_count"] == 2
    assert data["learning_run"]["success_adjustment_applied"] is True

    outcomes = manager.get("/api/model-feedback/outcomes")
    assert outcomes.status_code == 200, outcomes.text
    rows = outcomes.json()
    assert {row["asset_identifier"] for row in rows} >= {"CAR-001", "CAR-002"}
    assert all(row["source_type"] == "batch_feedback_upload" for row in rows)
