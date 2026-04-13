"""Test that Alembic can migrate a blank database to head."""
import os
import pytest
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic.command import upgrade


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
])


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
    alembic_cfg = Config(
        os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
    )

    upgrade(alembic_cfg, "head")

    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    engine.dispose()

    for tbl in REQUIRED_TABLES:
        assert tbl in tables, f"Missing table: {tbl}"
