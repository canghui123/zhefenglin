from services import valuation_control_service
from tests.services.commercial_test_helpers import create_tenant, make_session
from scripts.seed_commercial_defaults import seed_defaults


def test_evaluate_request_defaults_to_basic_when_no_trigger_matches():
    session = make_session()
    try:
        seed_defaults(session)
        tenant = create_tenant(session)
        session.commit()

        decision = valuation_control_service.evaluate_request(
            session,
            tenant_id=tenant.id,
            vehicle_value=80000,
            profit_margin=0.15,
            risk_tags=[],
            manual_selected=False,
            approval_mode=False,
        )

        assert decision["allow_condition_pricing"] is False
        assert decision["fallback_level"] == "basic"
        assert decision["matched_rule_types"] == []
    finally:
        session.close()


def test_evaluate_request_allows_condition_pricing_when_trigger_rule_matches():
    session = make_session()
    try:
        seed_defaults(session)
        tenant = create_tenant(session)
        session.commit()

        decision = valuation_control_service.evaluate_request(
            session,
            tenant_id=tenant.id,
            vehicle_value=220000,
            profit_margin=0.12,
            risk_tags=[],
            manual_selected=False,
            approval_mode=False,
        )

        assert decision["allow_condition_pricing"] is True
        assert "high_asset_value" in decision["matched_rule_types"]
        assert decision["fallback_level"] == "condition_pricing"
    finally:
        session.close()


def test_evaluate_request_allows_condition_pricing_in_approval_mode():
    session = make_session()
    try:
        seed_defaults(session)
        tenant = create_tenant(session)
        session.commit()

        decision = valuation_control_service.evaluate_request(
            session,
            tenant_id=tenant.id,
            vehicle_value=50000,
            profit_margin=0.2,
            risk_tags=[],
            manual_selected=False,
            approval_mode=True,
        )

        assert decision["allow_condition_pricing"] is True
        assert "approval_report_mode" in decision["matched_rule_types"]
    finally:
        session.close()
