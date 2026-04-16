from db.models.usage import UsageEvent
from services import quota_service
from tests.services.commercial_test_helpers import (
    create_tenant,
    make_session,
    seed_subscription,
)


def test_check_allowance_allows_usage_when_quota_and_budget_are_available():
    session = make_session()
    try:
        tenant = create_tenant(session)
        seed_subscription(session, tenant_id=tenant.id, plan_code="standard")
        session.commit()

        decision = quota_service.check_allowance(
            session,
            tenant_id=tenant.id,
            resource_type="vin_call",
            requested_quantity=1,
            estimated_internal_cost=1.5,
        )

        assert decision["allowed"] is True
        assert decision["reason"] is None
        assert decision["quota_limit"] == 1000
        assert decision["quota_used"] == 0
        assert decision["quota_remaining"] == 1000
    finally:
        session.close()


def test_check_allowance_blocks_when_monthly_quota_is_exhausted():
    session = make_session()
    try:
        tenant = create_tenant(session)
        seed_subscription(session, tenant_id=tenant.id, plan_code="trial_poc")
        session.add(
            UsageEvent(
                tenant_id=tenant.id,
                user_id=None,
                module="asset-pricing",
                action="vin_valuation",
                resource_type="vin_call",
                quantity=120,
                unit_cost_internal=1.5,
                unit_price_external=0,
                estimated_cost_total=180,
            )
        )
        session.commit()

        decision = quota_service.check_allowance(
            session,
            tenant_id=tenant.id,
            resource_type="vin_call",
            requested_quantity=1,
            estimated_internal_cost=1.5,
        )

        assert decision["allowed"] is False
        assert decision["reason"] == "quota_exceeded"
        assert decision["quota_limit"] == 120
        assert decision["quota_used"] == 120
        assert decision["quota_remaining"] == 0
    finally:
        session.close()


def test_check_allowance_blocks_when_budget_or_task_budget_would_be_exceeded():
    session = make_session()
    try:
        tenant = create_tenant(session)
        seed_subscription(
            session,
            tenant_id=tenant.id,
            plan_code="standard",
            monthly_budget_limit=100,
        )
        session.add(
            UsageEvent(
                tenant_id=tenant.id,
                user_id=None,
                module="asset-pricing",
                action="condition_pricing",
                resource_type="condition_pricing",
                quantity=2,
                unit_cost_internal=36,
                unit_price_external=0,
                estimated_cost_total=72,
            )
        )
        session.commit()

        monthly_budget_decision = quota_service.check_allowance(
            session,
            tenant_id=tenant.id,
            resource_type="condition_pricing",
            requested_quantity=1,
            estimated_internal_cost=36,
        )
        task_budget_decision = quota_service.check_allowance(
            session,
            tenant_id=tenant.id,
            resource_type="condition_pricing",
            requested_quantity=1,
            estimated_internal_cost=36,
            single_task_budget=20,
        )

        assert monthly_budget_decision["allowed"] is False
        assert monthly_budget_decision["reason"] == "monthly_budget_exceeded"
        assert task_budget_decision["allowed"] is False
        assert task_budget_decision["reason"] == "single_task_budget_exceeded"
    finally:
        session.close()
