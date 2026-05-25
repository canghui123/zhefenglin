"""Test that Alembic can migrate a blank database to head."""
import os
import pytest
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic.command import check, upgrade


REQUIRED_TABLES = sorted([
    "car_models",
    "valuation_cache",
    "asset_packages",
    "assets",
    "depreciation_cache",
    "sandbox_results",
    "portfolio_snapshots",
    "asset_segments",
    "segment_metrics",
    "strategy_runs",
    "cashflow_buckets",
    "management_goals",
    "recommended_actions",
    "users",
    "user_sessions",
    "tenants",
    "memberships",
    "audit_logs",
    "job_runs",
    "plans",
    "tenant_subscriptions",
    "feature_entitlements",
    "usage_events",
    "cost_snapshots",
    "model_routing_rules",
    "valuation_trigger_rules",
    "approval_requests",
    "tenant_deployment_profiles",
    "brand_retention_profiles",
    "region_disposal_coefficients",
    "work_orders",
    "disposal_outcomes",
    "model_learning_runs",
    "data_import_batches",
    "data_import_rows",
    "sandbox_simulation_batches",
    "sandbox_simulation_batch_items",
    "agent_runs",
    "agent_tasks",
    "agent_recommendations",
    "decision_audit_logs",
    "agent_rule_settings",
    "agent_run_reviews",
])


def _alembic_config() -> Config:
    base_dir = os.path.join(os.path.dirname(__file__), "..", "..")
    alembic_cfg = Config(os.path.join(base_dir, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(base_dir, "alembic"))
    return alembic_cfg


@pytest.fixture()
def test_db_url():
    """Use the test PostgreSQL database, creating a clean schema."""
    base_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://app:app@localhost:5432/auto_finance",
    )
    engine = create_engine(base_url)
    schema = f"test_{os.getpid()}"
    with engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        conn.commit()
    yield f"{base_url}?options=-csearch_path%3D{schema}"
    with engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        conn.commit()
    engine.dispose()


def test_alembic_can_upgrade_to_head(test_db_url, monkeypatch):
    """Running alembic upgrade head on a blank schema creates all tables."""
    monkeypatch.setenv("DATABASE_URL", test_db_url)
    alembic_cfg = _alembic_config()

    upgrade(alembic_cfg, "head")

    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    engine.dispose()

    for tbl in REQUIRED_TABLES:
        assert tbl in tables, f"Missing table: {tbl}"


def test_tenant_deployment_profile_constraints_and_foreign_keys(test_db_url, monkeypatch):
    """The deployment profile table should enforce its tenant and user links."""
    monkeypatch.setenv("DATABASE_URL", test_db_url)
    alembic_cfg = _alembic_config()

    upgrade(alembic_cfg, "head")

    engine = create_engine(test_db_url)
    inspector = inspect(engine)

    unique_constraints = inspector.get_unique_constraints("tenant_deployment_profiles")
    unique_cols = {
        tuple(constraint["column_names"])
        for constraint in unique_constraints
    }
    assert ("tenant_id",) in unique_cols

    fk_map = {
        tuple(fk["constrained_columns"]): fk["referred_table"]
        for fk in inspector.get_foreign_keys("tenant_deployment_profiles")
    }
    assert fk_map[("tenant_id",)] == "tenants"
    assert fk_map[("created_by",)] == "users"
    assert fk_map[("updated_by",)] == "users"

    engine.dispose()


def test_decision_audit_log_decision_type_is_required(test_db_url, monkeypatch):
    """Agent audit logs separate decision type from action for reporting."""
    monkeypatch.setenv("DATABASE_URL", test_db_url)
    alembic_cfg = _alembic_config()

    upgrade(alembic_cfg, "head")

    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    columns = {
        column["name"]: column
        for column in inspector.get_columns("decision_audit_logs")
    }

    assert columns["decision_type"]["nullable"] is False
    assert columns["action"]["nullable"] is False

    engine.dispose()


def test_agent_governance_tables_have_tenant_boundaries(test_db_url, monkeypatch):
    """AI Agent settings and reviews must stay tenant-scoped."""
    monkeypatch.setenv("DATABASE_URL", test_db_url)
    alembic_cfg = _alembic_config()

    upgrade(alembic_cfg, "head")

    engine = create_engine(test_db_url)
    inspector = inspect(engine)

    settings_uniques = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("agent_rule_settings")
    }
    assert ("tenant_id", "agent_type", "scenario", "version") in settings_uniques

    settings_columns = {
        column["name"]: column
        for column in inspector.get_columns("agent_rule_settings")
    }
    assert settings_columns["tenant_id"]["nullable"] is False
    assert settings_columns["agent_type"]["nullable"] is False
    assert settings_columns["scenario"]["nullable"] is False
    assert settings_columns["version"]["nullable"] is False
    assert settings_columns["is_active"]["nullable"] is False

    review_columns = {
        column["name"]: column
        for column in inspector.get_columns("agent_run_reviews")
    }
    assert review_columns["tenant_id"]["nullable"] is False
    assert review_columns["agent_run_id"]["nullable"] is False
    assert review_columns["outcome"]["nullable"] is False

    engine.dispose()


def test_alembic_autogenerate_has_no_metadata_drift(test_db_url, monkeypatch):
    """A schema upgraded to head should be in sync with ORM metadata."""
    monkeypatch.setenv("DATABASE_URL", test_db_url)
    alembic_cfg = _alembic_config()

    upgrade(alembic_cfg, "head")
    check(alembic_cfg)
