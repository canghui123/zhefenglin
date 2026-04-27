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
