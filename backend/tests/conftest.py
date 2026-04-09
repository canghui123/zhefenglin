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


def _seed_user(
    email: str,
    role: str,
    password: str = "Passw0rd!",
    *,
    tenant_code: str = "default",
) -> int:
    """Helper used by both the fixture and direct callers.

    Always provisions a default tenant + membership so the resulting user
    can hit business endpoints (which require `default_tenant_id`).
    """
    from db.session import get_db_session
    from repositories import user_repo, tenant_repo
    from services.password_service import hash_password

    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_or_create_tenant(
            session, code=tenant_code, name=tenant_code.upper()
        )
        user = user_repo.create_user(
            session,
            email=email,
            password_hash=hash_password(password),
            role=role,
            display_name=role,
        )
        tenant_repo.create_membership(
            session, user_id=user.id, tenant_id=tenant.id, role=role
        )
        user_repo.set_default_tenant(session, user.id, tenant.id)
        session.commit()
        return user.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


@pytest.fixture
def authed_client():
    """Return a TestClient already logged in as an `operator` user.

    Existing tests for the business endpoints (asset-package, sandbox)
    don't care about the role beyond "is allowed to write" — operator
    is the lowest role that can run uploads/simulate, so we use it.
    """
    from fastapi.testclient import TestClient
    from main import app

    _seed_user("test-operator@example.com", role="operator")
    client = TestClient(app)
    response = client.post(
        "/api/auth/login",
        json={"email": "test-operator@example.com", "password": "Passw0rd!"},
    )
    assert response.status_code == 200, response.text
    # The login endpoint sets the session cookie on the client; the same
    # client now carries auth on every subsequent request.
    return client
