from fastapi.testclient import TestClient

from db.session import get_db_session
from main import app
from repositories import tenant_repo, user_repo
from services.password_service import hash_password


def _seed_user(*, email: str, role: str = "operator", tenant_code: str = "legal"):
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


def _document_payload(**overrides):
    payload = {
        "document_type": "civil_complaint",
        "debtor_name": "张三",
        "creditor_name": "车途金融",
        "car_description": "奔驰E级 2021款",
        "contract_number": "HT-2026-001",
        "overdue_amount": 180000,
        "vehicle_value": 260000,
    }
    payload.update(overrides)
    return payload


def test_operator_can_generate_legal_document(authed_client):
    response = authed_client.post(
        "/api/legal-documents/generate",
        json=_document_payload(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "民事起诉状"
    assert "奔驰E级" in body["html"]
    assert body["work_order_id"] is None


def test_generate_legal_document_completes_related_work_order(authed_client):
    created = authed_client.post(
        "/api/work-orders",
        json={
            "order_type": "legal_document",
            "title": "生成起诉材料：张三",
            "priority": "high",
            "payload": {"debtor_name": "张三"},
        },
    )
    assert created.status_code == 200, created.text
    work_order_id = created.json()["id"]

    generated = authed_client.post(
        "/api/legal-documents/generate",
        json=_document_payload(work_order_id=work_order_id),
    )
    assert generated.status_code == 200, generated.text
    assert generated.json()["work_order_id"] == work_order_id

    fetched = authed_client.get(f"/api/work-orders/{work_order_id}")
    assert fetched.status_code == 200, fetched.text
    body = fetched.json()
    assert body["status"] == "completed"
    assert body["result"]["document_type"] == "civil_complaint"
    assert body["result"]["title"] == "民事起诉状"


def test_generate_legal_document_rejects_non_legal_work_order(authed_client):
    created = authed_client.post(
        "/api/work-orders",
        json={
            "order_type": "towing",
            "title": "委外拖车",
            "payload": {},
        },
    )
    assert created.status_code == 200, created.text

    response = authed_client.post(
        "/api/legal-documents/generate",
        json=_document_payload(work_order_id=created.json()["id"]),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_LEGAL_DOCUMENT_REQUEST"


def test_viewer_cannot_generate_legal_document():
    _seed_user(email="viewer-legal@example.com", role="viewer")
    client = _login("viewer-legal@example.com")

    response = client.post(
        "/api/legal-documents/generate",
        json=_document_payload(),
    )

    assert response.status_code == 403
