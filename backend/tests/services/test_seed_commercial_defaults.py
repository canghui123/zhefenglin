from sqlalchemy import func, select

from db.models.model_routing import ModelRoutingRule
from db.models.plan import Plan
from db.models.subscription import FeatureEntitlement
from db.models.valuation_control import ValuationTriggerRule
from db.session import get_sessionmaker, reset_engine
from scripts.seed_commercial_defaults import seed_defaults


def _get_session():
    reset_engine()
    SessionLocal = get_sessionmaker()
    return SessionLocal()


def test_seed_defaults_creates_expected_plans_and_entitlements():
    session = _get_session()
    try:
        seed_defaults(session)
        session.commit()

        plans = {
            plan.code: plan
            for plan in session.scalars(select(Plan).order_by(Plan.id)).all()
        }
        assert set(plans) == {
            "trial_poc",
            "standard",
            "pro_manager",
            "enterprise_private",
        }

        assert plans["trial_poc"].name == "Trial / POC"
        assert plans["standard"].included_vin_calls > plans["trial_poc"].included_vin_calls
        assert (
            plans["pro_manager"].included_condition_pricing_points
            > plans["standard"].included_condition_pricing_points
        )
        assert plans["enterprise_private"].private_deploy_fee > 0

        entitlements = list(
            session.scalars(
                select(FeatureEntitlement).where(FeatureEntitlement.scope == "plan")
            ).all()
        )
        assert entitlements
        feature_keys = {entitlement.feature_key for entitlement in entitlements}
        assert "dashboard.advanced" in feature_keys
        assert "audit.export" in feature_keys
        assert "deployment.private_config" in feature_keys
    finally:
        session.close()


def test_seed_defaults_is_idempotent_and_creates_global_rules():
    session = _get_session()
    try:
        seed_defaults(session)
        seed_defaults(session)
        session.commit()

        assert session.scalar(select(func.count()).select_from(Plan)) == 4
        assert (
            session.scalar(select(func.count()).select_from(ModelRoutingRule)) >= 4
        )
        assert (
            session.scalar(select(func.count()).select_from(ValuationTriggerRule)) >= 5
        )

        routing_rules = list(
            session.scalars(
                select(ModelRoutingRule)
                .where(ModelRoutingRule.scope == "global")
                .order_by(ModelRoutingRule.task_type)
            ).all()
        )
        task_types = {rule.task_type for rule in routing_rules}
        assert "light_task" in task_types
        assert "medium_task" in task_types
        assert "long_text" in task_types

        trigger_rules = list(
            session.scalars(
                select(ValuationTriggerRule)
                .where(ValuationTriggerRule.scope == "global")
                .order_by(ValuationTriggerRule.trigger_type)
            ).all()
        )
        trigger_types = {rule.trigger_type for rule in trigger_rules}
        assert "profit_margin_threshold" in trigger_types
        assert "high_asset_value" in trigger_types
        assert "high_risk_vehicle" in trigger_types
        assert "manual_request" in trigger_types
        assert "approval_report_mode" in trigger_types
    finally:
        session.close()
