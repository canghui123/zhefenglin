from sqlalchemy import select

from db.models.usage import CostSnapshot, UsageEvent
from services import cost_metering_service
from tests.services.commercial_test_helpers import create_tenant, create_user, make_session


def test_record_usage_writes_usage_event():
    session = make_session()
    try:
        tenant = create_tenant(session)
        user = create_user(session, email="meter@example.com")

        event = cost_metering_service.record_usage(
            session,
            tenant_id=tenant.id,
            user_id=user.id,
            module="asset-pricing",
            action="vin_valuation",
            resource_type="vin_call",
            quantity=1,
            unit_cost_internal=1.5,
            unit_price_external=3.0,
            request_id="req-usage-1",
            related_object_type="asset_package",
            related_object_id="12",
            metadata={"source": "unit-test"},
        )
        session.commit()

        saved = session.scalars(
            select(UsageEvent).where(UsageEvent.id == event.id).limit(1)
        ).first()
        assert saved is not None
        assert saved.request_id == "req-usage-1"
        assert saved.estimated_cost_total == 1.5
    finally:
        session.close()


def test_record_usage_updates_monthly_cost_snapshot():
    session = make_session()
    try:
        tenant = create_tenant(session)
        user = create_user(session, email="snapshot@example.com")

        cost_metering_service.record_usage(
            session,
            tenant_id=tenant.id,
            user_id=user.id,
            module="car-valuation",
            action="vin_valuation",
            resource_type="vin_call",
            quantity=2,
            unit_cost_internal=1.5,
            unit_price_external=4.0,
            extra_snapshot_metrics={"estimated_revenue": 8.0},
        )
        cost_metering_service.record_usage(
            session,
            tenant_id=tenant.id,
            user_id=user.id,
            module="asset-pricing",
            action="llm_report",
            resource_type="llm_completion",
            quantity=1,
            unit_cost_internal=0.8,
            unit_price_external=0,
            extra_snapshot_metrics={
                "llm_input_tokens": 1200,
                "llm_output_tokens": 300,
                "llm_cost": 0.8,
            },
        )
        session.commit()

        snapshot = session.scalars(select(CostSnapshot).limit(1)).first()
        assert snapshot is not None
        assert snapshot.vin_calls == 2
        assert snapshot.llm_input_tokens == 1200
        assert snapshot.llm_output_tokens == 300
        assert snapshot.che300_cost == 3.0
        assert snapshot.llm_cost == 0.8
        assert snapshot.total_cost == 3.8
        assert snapshot.estimated_revenue == 8.0
        assert snapshot.estimated_gross_profit == 4.2
    finally:
        session.close()
