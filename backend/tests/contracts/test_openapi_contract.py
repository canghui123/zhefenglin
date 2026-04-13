"""Task 10 — OpenAPI contract smoke tests.

Ensures critical API paths remain present in the generated schema and
that auth/error models are included.
"""
from fastapi.testclient import TestClient

from main import app


def test_openapi_schema_is_valid():
    client = TestClient(app)
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert "paths" in schema
    assert "info" in schema


def test_critical_paths_exist_in_schema():
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    required_paths = [
        "/api/health",
        "/api/auth/login",
        "/api/asset-package/upload",
        "/api/asset-package/calculate",
        "/api/sandbox/simulate",
        "/api/jobs/{job_id}",
        "/api/metrics",
    ]
    for p in required_paths:
        assert p in paths, f"Missing path: {p}"


def test_openapi_includes_error_schema():
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    components = schema.get("components", {}).get("schemas", {})
    assert "ErrorEnvelope" in components, "ErrorEnvelope schema missing"
