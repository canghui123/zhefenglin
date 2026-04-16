import json

from sqlalchemy import select

from db.models.usage import UsageEvent
from db.models.subscription import TenantSubscription
from db.session import get_db_session
from repositories import tenant_repo
from scripts.seed_commercial_defaults import seed_defaults
from services import che300_client


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
