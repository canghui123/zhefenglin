import json
import os

from sqlalchemy import select

from db.models.valuation_control import ApprovalRequest
from db.models.usage import UsageEvent
from db.models.subscription import TenantSubscription
from db.session import get_db_session
from repositories import tenant_repo
from scripts.seed_commercial_defaults import seed_defaults
from services import approval_service, che300_client

SAMPLE_EXCEL = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "sample_asset_package.xlsx"
)


def _seed_default_subscription(
    *,
    plan_code: str = "standard",
    monthly_budget_limit: float = 5000,
):
    from db.models.plan import Plan

    gen = get_db_session()
    session = next(gen)
    try:
        seed_defaults(session)
        tenant = tenant_repo.get_tenant_by_code(session, "default")
        if tenant is None:
            tenant = tenant_repo.get_or_create_tenant(
                session, code="default", name="DEFAULT"
            )

        existing = session.scalars(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant.id)
            .where(TenantSubscription.is_current.is_(True))
            .limit(1)
        ).first()
        if existing is not None:
            existing.is_current = False

        plan = session.scalars(select(Plan).where(Plan.code == plan_code).limit(1)).first()
        session.add(
            TenantSubscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="active",
                monthly_budget_limit=monthly_budget_limit,
                alert_threshold_percent=80,
                is_current=True,
            )
        )
        session.commit()
        return tenant.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _read_usage_events():
    gen = get_db_session()
    session = next(gen)
    try:
        return list(session.scalars(select(UsageEvent).order_by(UsageEvent.id)).all())
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _create_approved_request(*, tenant_id: int, related_object_type: str, related_object_id: str):
    from db.models.user import User

    gen = get_db_session()
    session = next(gen)
    try:
        applicant = session.scalars(
            select(User).where(User.email == "approval-applicant@example.com").limit(1)
        ).first()
        if applicant is None:
            applicant = User(
                email="approval-applicant@example.com",
                password_hash="not-used",
                role="manager",
                display_name="approval-applicant",
            )
            session.add(applicant)
            session.flush()

        approver = session.scalars(
            select(User).where(User.email == "approval-admin@example.com").limit(1)
        ).first()
        if approver is None:
            approver = User(
                email="approval-admin@example.com",
                password_hash="not-used",
                role="admin",
                display_name="approval-admin",
            )
            session.add(approver)
            session.flush()

        request = approval_service.create_request(
            session,
            tenant_id=tenant_id,
            applicant_user_id=applicant.id,
            type="condition_pricing",
            reason="Manual approval for advanced pricing",
            related_object_type=related_object_type,
            related_object_id=related_object_id,
            estimated_cost=36,
            metadata={"source": "test"},
        )
        session.flush()
        approval_service.approve(
            session,
            approval_request_id=request.id,
            approver_user_id=approver.id,
            actual_cost=36,
        )
        session.commit()
        return request.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _read_approval_request(approval_request_id: int):
    gen = get_db_session()
    session = next(gen)
    try:
        return session.get(ApprovalRequest, approval_request_id)
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _upload_sample_package(authed_client) -> int:
    with open(SAMPLE_EXCEL, "rb") as handle:
        response = authed_client.post(
            "/api/asset-package/upload",
            files={
                "file": (
                    "guardrails.xlsx",
                    handle,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert response.status_code == 200, response.text
    return response.json()["package_id"]


def test_condition_pricing_budget_check_returns_structured_error(authed_client, monkeypatch):
    monkeypatch.setattr(che300_client.settings, "che300_access_key", "")
    monkeypatch.setattr(che300_client.settings, "che300_access_secret", "")
    _seed_default_subscription(monthly_budget_limit=5000)

    response = authed_client.post(
        "/api/valuation/single",
        json={
            "model_id": "WVWZZZ3CZWE123456",
            "registration_date": "2020-01",
            "mileage": 6.2,
            "advanced_condition_pricing": True,
            "approval_mode": True,
            "strict_policy": True,
            "single_task_budget": 20,
        },
    )

    assert response.status_code == 409, response.text
    payload = response.json()["error"]
    assert payload["code"] == "BUDGET_EXCEEDED"
    assert payload["details"]["fallback_action"] == "回退基础VIN估值 + AI解释"
    assert payload["details"]["approval_context"]["approval_type"] == "condition_pricing"
    assert payload["details"]["approval_context"]["related_object_type"] == "vehicle"
    assert payload["details"]["approval_context"]["related_object_id"] == "WVWZZZ3CZWE123456"


def test_condition_pricing_falls_back_to_basic_and_records_usage_event(authed_client, monkeypatch):
    monkeypatch.setattr(che300_client.settings, "che300_access_key", "")
    monkeypatch.setattr(che300_client.settings, "che300_access_secret", "")
    _seed_default_subscription(monthly_budget_limit=5000)

    response = authed_client.post(
        "/api/valuation/single",
        json={
            "model_id": "WVWZZZ3CZWE123456",
            "registration_date": "2020-01",
            "mileage": 5.5,
            "advanced_condition_pricing": True,
            "strict_policy": False,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["model_id"]

    usage_events = _read_usage_events()
    valuation_events = [event for event in usage_events if event.module == "car-valuation"]
    assert valuation_events
    latest = valuation_events[-1]
    assert latest.resource_type == "vin_call"
    metadata = json.loads(latest.metadata_json)
    assert metadata["requested_level"] == "condition_pricing"
    assert metadata["executed_level"] == "basic"
    assert metadata["degraded"] is True


def test_condition_pricing_allows_execution_with_approved_request_and_consumes_it(
    authed_client, monkeypatch
):
    monkeypatch.setattr(che300_client.settings, "che300_access_key", "")
    monkeypatch.setattr(che300_client.settings, "che300_access_secret", "")
    tenant_id = _seed_default_subscription(monthly_budget_limit=5000)
    approval_request_id = _create_approved_request(
        tenant_id=tenant_id,
        related_object_type="vehicle",
        related_object_id="WVWZZZ3CZWE123456",
    )

    response = authed_client.post(
        "/api/valuation/single",
        json={
            "model_id": "WVWZZZ3CZWE123456",
            "registration_date": "2020-01",
            "mileage": 5.5,
            "advanced_condition_pricing": True,
            "strict_policy": True,
            "approval_request_id": approval_request_id,
        },
    )

    assert response.status_code == 200, response.text

    approval_row = _read_approval_request(approval_request_id)
    assert approval_row.consumed_at is not None
    assert approval_row.consumed_request_id is not None

    usage_events = _read_usage_events()
    valuation_events = [event for event in usage_events if event.module == "car-valuation"]
    latest = valuation_events[-1]
    metadata = json.loads(latest.metadata_json)
    assert metadata["executed_level"] == "condition_pricing"
    assert metadata["approval_request_id"] == approval_request_id
    assert metadata["approval_granted"] is True


def test_asset_package_suggest_buyout_returns_package_level_approval_context(
    authed_client, monkeypatch
):
    monkeypatch.setattr(che300_client.settings, "che300_access_key", "")
    monkeypatch.setattr(che300_client.settings, "che300_access_secret", "")
    _seed_default_subscription(monthly_budget_limit=5000)
    package_id = _upload_sample_package(authed_client)

    response = authed_client.post(
        "/api/asset-package/suggest-buyout",
        json={
            "package_id": package_id,
            "vehicle_condition": "good",
            "advanced_condition_pricing": True,
            "strict_policy": True,
        },
    )

    assert response.status_code == 409, response.text
    payload = response.json()["error"]
    assert payload["details"]["approval_context"]["related_object_type"] == "asset_package"
    assert payload["details"]["approval_context"]["related_object_id"] == str(package_id)
