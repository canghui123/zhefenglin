import os
import tempfile
import pytest


@pytest.fixture(autouse=True)
def isolated_backend_env(monkeypatch):
    """Isolate each test with a temp SQLite DB (used by the SQLAlchemy layer)
    and a fresh upload dir."""
    with tempfile.TemporaryDirectory() as tmp:
        db_file = os.path.join(tmp, "test.db")
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
        monkeypatch.setenv("DATABASE_PATH", db_file)
        monkeypatch.setenv("UPLOAD_DIR", os.path.join(tmp, "uploads"))

        # Rebuild the lazy engine against the new DATABASE_URL and create
        # all tables via SQLAlchemy metadata (we skip Alembic for speed).
        from db.session import reset_engine, get_engine
        from db.base import Base
        import db.models  # noqa: F401 — registers all ORM models

        reset_engine()
        engine = get_engine()
        Base.metadata.create_all(engine)

        yield

        reset_engine()
