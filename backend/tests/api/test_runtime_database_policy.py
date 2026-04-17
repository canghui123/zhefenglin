"""Runtime database policy regression tests.

The commercial runtime path is PostgreSQL-only. Legacy SQLite bootstrap
must not be triggered just because DATABASE_PATH is present in the env.
"""
import os

from fastapi.testclient import TestClient

import main


def test_health_startup_does_not_bootstrap_legacy_sqlite_from_database_path(
    monkeypatch, tmp_path
):
    legacy_db = tmp_path / "legacy-runtime.db"

    monkeypatch.setenv("DATABASE_PATH", str(legacy_db))
    monkeypatch.setattr(main.settings, "database_path", str(legacy_db))
    monkeypatch.setattr(
        main.settings,
        "database_url",
        "postgresql+psycopg://app:app@localhost:5432/auto_finance",
    )

    assert not legacy_db.exists()

    with TestClient(main.app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert not legacy_db.exists()

    os.environ.pop("DATABASE_PATH", None)
