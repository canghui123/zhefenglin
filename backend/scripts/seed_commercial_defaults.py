"""Seed default commercial control data.

Usage::

    cd backend
    python -m scripts.seed_commercial_defaults

Run after `alembic upgrade head`. The script is idempotent: existing plans,
feature entitlements, model routing rules, and valuation trigger rules are
updated in place instead of duplicated.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.model_routing import ModelRoutingRule
from db.models.plan import Plan
from db.models.subscription import FeatureEntitlement
from db.models.valuation_control import ValuationTriggerRule
from db.session import get_sessionmaker, reset_engine


DEFAULT_PLANS: list[dict[str, Any]] = [
    {
        "code": "trial_poc",
        "name": "Trial / POC",
        "billing_cycle_supported": "monthly",
        "monthly_price": 1999,
        "yearly_price": 19990,
        "setup_fee": 0,
        "private_deploy_fee": 0,
        "seat_limit": 3,
        "included_vin_calls": 120,
        "included_condition_pricing_points": 3,
        "included_ai_reports": 20,
        "included_asset_packages": 10,
        "included_sandbox_runs": 30,
        "overage_vin_unit_price": 2.5,
        "overage_condition_pricing_unit_price": 48,
        "feature_flags_json": json.dumps(
            {
                "dashboard.advanced": False,
                "audit.export": False,
                "deployment.private_config": False,
                "portfolio.advanced_pages": False,
                "tenant.value_dashboard": True,
            },
            sort_keys=True,
        ),
        "is_active": True,
    },
    {
        "code": "standard",
        "name": "Standard",
        "billing_cycle_supported": "monthly,yearly",
        "monthly_price": 6999,
        "yearly_price": 69990,
        "setup_fee": 5000,
        "private_deploy_fee": 0,
        "seat_limit": 10,
        "included_vin_calls": 1000,
        "included_condition_pricing_points": 20,
        "included_ai_reports": 200,
        "included_asset_packages": 100,
        "included_sandbox_runs": 300,
        "overage_vin_unit_price": 1.8,
        "overage_condition_pricing_unit_price": 42,
        "feature_flags_json": json.dumps(
            {
                "dashboard.advanced": True,
                "audit.export": False,
                "deployment.private_config": False,
                "portfolio.advanced_pages": False,
                "tenant.value_dashboard": True,
            },
            sort_keys=True,
        ),
        "is_active": True,
    },
    {
        "code": "pro_manager",
        "name": "Pro / Manager",
        "billing_cycle_supported": "monthly,yearly",
        "monthly_price": 15999,
        "yearly_price": 159990,
        "setup_fee": 10000,
        "private_deploy_fee": 0,
        "seat_limit": 30,
        "included_vin_calls": 5000,
        "included_condition_pricing_points": 120,
        "included_ai_reports": 1200,
        "included_asset_packages": 600,
        "included_sandbox_runs": 1600,
        "overage_vin_unit_price": 1.5,
        "overage_condition_pricing_unit_price": 38,
        "feature_flags_json": json.dumps(
            {
                "dashboard.advanced": True,
                "audit.export": True,
                "deployment.private_config": False,
                "portfolio.advanced_pages": True,
                "tenant.value_dashboard": True,
            },
            sort_keys=True,
        ),
        "is_active": True,
    },
    {
        "code": "enterprise_private",
        "name": "Enterprise / Private",
        "billing_cycle_supported": "monthly,yearly,custom",
        "monthly_price": 39999,
        "yearly_price": 399990,
        "setup_fee": 30000,
        "private_deploy_fee": 120000,
        "seat_limit": 200,
        "included_vin_calls": 20000,
        "included_condition_pricing_points": 500,
        "included_ai_reports": 5000,
        "included_asset_packages": 3000,
        "included_sandbox_runs": 10000,
        "overage_vin_unit_price": 1.2,
        "overage_condition_pricing_unit_price": 32,
        "feature_flags_json": json.dumps(
            {
                "dashboard.advanced": True,
                "audit.export": True,
                "deployment.private_config": True,
                "portfolio.advanced_pages": True,
                "tenant.value_dashboard": True,
                "pricing.custom_quote": True,
            },
            sort_keys=True,
        ),
        "is_active": True,
    },
]

DEFAULT_FEATURE_ENTITLEMENTS: list[dict[str, Any]] = [
    {"plan_code": "trial_poc", "feature_key": "dashboard.advanced", "is_enabled": False},
    {"plan_code": "trial_poc", "feature_key": "audit.export", "is_enabled": False},
    {
        "plan_code": "trial_poc",
        "feature_key": "deployment.private_config",
        "is_enabled": False,
    },
    {
        "plan_code": "trial_poc",
        "feature_key": "portfolio.advanced_pages",
        "is_enabled": False,
    },
    {"plan_code": "trial_poc", "feature_key": "tenant.value_dashboard", "is_enabled": True},
    {"plan_code": "standard", "feature_key": "dashboard.advanced", "is_enabled": True},
    {"plan_code": "standard", "feature_key": "audit.export", "is_enabled": False},
    {
        "plan_code": "standard",
        "feature_key": "deployment.private_config",
        "is_enabled": False,
    },
    {
        "plan_code": "standard",
        "feature_key": "portfolio.advanced_pages",
        "is_enabled": False,
    },
    {"plan_code": "standard", "feature_key": "tenant.value_dashboard", "is_enabled": True},
    {"plan_code": "pro_manager", "feature_key": "dashboard.advanced", "is_enabled": True},
    {"plan_code": "pro_manager", "feature_key": "audit.export", "is_enabled": True},
    {
        "plan_code": "pro_manager",
        "feature_key": "deployment.private_config",
        "is_enabled": False,
    },
    {
        "plan_code": "pro_manager",
        "feature_key": "portfolio.advanced_pages",
        "is_enabled": True,
    },
    {
        "plan_code": "pro_manager",
        "feature_key": "routing.model_control",
        "is_enabled": True,
    },
    {
        "plan_code": "pro_manager",
        "feature_key": "tenant.value_dashboard",
        "is_enabled": True,
    },
    {
        "plan_code": "enterprise_private",
        "feature_key": "dashboard.advanced",
        "is_enabled": True,
    },
    {
        "plan_code": "enterprise_private",
        "feature_key": "audit.export",
        "is_enabled": True,
    },
    {
        "plan_code": "enterprise_private",
        "feature_key": "deployment.private_config",
        "is_enabled": True,
    },
    {
        "plan_code": "enterprise_private",
        "feature_key": "portfolio.advanced_pages",
        "is_enabled": True,
    },
    {
        "plan_code": "enterprise_private",
        "feature_key": "routing.model_control",
        "is_enabled": True,
    },
    {
        "plan_code": "enterprise_private",
        "feature_key": "tenant.value_dashboard",
        "is_enabled": True,
    },
]

DEFAULT_MODEL_ROUTING_RULES: list[dict[str, Any]] = [
    {
        "scope": "global",
        "tenant_id": None,
        "task_type": "light_task",
        "preferred_model": "qwen-turbo",
        "fallback_model": "qwen-plus",
        "allow_batch": True,
        "allow_search": False,
        "allow_high_cost_mode": False,
        "prompt_version": "v1",
        "is_active": True,
        "created_by": None,
    },
    {
        "scope": "global",
        "tenant_id": None,
        "task_type": "medium_task",
        "preferred_model": "qwen-plus",
        "fallback_model": "qwen-turbo",
        "allow_batch": True,
        "allow_search": False,
        "allow_high_cost_mode": False,
        "prompt_version": "v1",
        "is_active": True,
        "created_by": None,
    },
    {
        "scope": "global",
        "tenant_id": None,
        "task_type": "long_text",
        "preferred_model": "qwen-long",
        "fallback_model": "qwen-plus",
        "allow_batch": False,
        "allow_search": False,
        "allow_high_cost_mode": False,
        "prompt_version": "v1",
        "is_active": True,
        "created_by": None,
    },
    {
        "scope": "global",
        "tenant_id": None,
        "task_type": "report_generation",
        "preferred_model": "qwen-plus",
        "fallback_model": "qwen-turbo",
        "allow_batch": False,
        "allow_search": False,
        "allow_high_cost_mode": True,
        "prompt_version": "v1",
        "is_active": True,
        "created_by": None,
    },
]

DEFAULT_VALUATION_TRIGGER_RULES: list[dict[str, Any]] = [
    {
        "scope": "global",
        "tenant_id": None,
        "enabled": True,
        "trigger_type": "profit_margin_threshold",
        "trigger_config_json": json.dumps(
            {"margin_lower_bound": 0.03, "margin_upper_bound": 0.08},
            sort_keys=True,
        ),
        "created_by": None,
    },
    {
        "scope": "global",
        "tenant_id": None,
        "enabled": True,
        "trigger_type": "high_asset_value",
        "trigger_config_json": json.dumps(
            {"min_vehicle_value": 150000},
            sort_keys=True,
        ),
        "created_by": None,
    },
    {
        "scope": "global",
        "tenant_id": None,
        "enabled": True,
        "trigger_type": "high_risk_vehicle",
        "trigger_config_json": json.dumps(
            {
                "risk_tags": [
                    "major_accident",
                    "fire_damage",
                    "flood_damage",
                    "legal_dispute",
                ]
            },
            sort_keys=True,
        ),
        "created_by": None,
    },
    {
        "scope": "global",
        "tenant_id": None,
        "enabled": True,
        "trigger_type": "manual_request",
        "trigger_config_json": json.dumps(
            {"requires_manual_selection": True},
            sort_keys=True,
        ),
        "created_by": None,
    },
    {
        "scope": "global",
        "tenant_id": None,
        "enabled": True,
        "trigger_type": "approval_report_mode",
        "trigger_config_json": json.dumps(
            {"requires_approval_mode": True},
            sort_keys=True,
        ),
        "created_by": None,
    },
]


def _upsert(session: Session, model: Any, filters: dict[str, Any], values: dict[str, Any]) -> bool:
    existing = session.scalars(select(model).filter_by(**filters).limit(1)).first()
    if existing is None:
        session.add(model(**filters, **values))
        session.flush()
        return True

    for field, value in values.items():
        setattr(existing, field, value)
    session.flush()
    return False


def seed_defaults(session: Session) -> dict[str, int]:
    summary = {
        "plans_created": 0,
        "plans_updated": 0,
        "entitlements_created": 0,
        "entitlements_updated": 0,
        "routes_created": 0,
        "routes_updated": 0,
        "rules_created": 0,
        "rules_updated": 0,
    }

    plan_by_code: dict[str, Plan] = {}
    for plan_data in DEFAULT_PLANS:
        filters = {"code": plan_data["code"]}
        values = {key: value for key, value in plan_data.items() if key != "code"}
        created = _upsert(session, Plan, filters, values)
        summary["plans_created" if created else "plans_updated"] += 1

    for plan in session.scalars(select(Plan)).all():
        plan_by_code[plan.code] = plan

    for entitlement_data in DEFAULT_FEATURE_ENTITLEMENTS:
        plan = plan_by_code[entitlement_data["plan_code"]]
        filters = {
            "scope": "plan",
            "plan_id": plan.id,
            "tenant_id": None,
            "feature_key": entitlement_data["feature_key"],
        }
        values = {
            "is_enabled": entitlement_data["is_enabled"],
            "config_json": entitlement_data.get("config_json"),
        }
        created = _upsert(session, FeatureEntitlement, filters, values)
        summary["entitlements_created" if created else "entitlements_updated"] += 1

    for route_data in DEFAULT_MODEL_ROUTING_RULES:
        filters = {
            "scope": route_data["scope"],
            "tenant_id": route_data["tenant_id"],
            "task_type": route_data["task_type"],
        }
        values = {
            key: value
            for key, value in route_data.items()
            if key not in {"scope", "tenant_id", "task_type"}
        }
        created = _upsert(session, ModelRoutingRule, filters, values)
        summary["routes_created" if created else "routes_updated"] += 1

    for rule_data in DEFAULT_VALUATION_TRIGGER_RULES:
        filters = {
            "scope": rule_data["scope"],
            "tenant_id": rule_data["tenant_id"],
            "trigger_type": rule_data["trigger_type"],
        }
        values = {
            key: value
            for key, value in rule_data.items()
            if key not in {"scope", "tenant_id", "trigger_type"}
        }
        created = _upsert(session, ValuationTriggerRule, filters, values)
        summary["rules_created" if created else "rules_updated"] += 1

    return summary


def main() -> int:
    reset_engine()
    SessionLocal = get_sessionmaker()
    session = SessionLocal()
    try:
        summary = seed_defaults(session)
        session.commit()
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
