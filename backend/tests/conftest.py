import os
import tempfile
import pytest


@pytest.fixture(autouse=True)
def isolated_backend_env(monkeypatch):
    """Isolate each test with a temporary database and upload dir."""
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("DATABASE_PATH", os.path.join(tmp, "test.db"))
        monkeypatch.setenv("UPLOAD_DIR", os.path.join(tmp, "uploads"))
        yield
