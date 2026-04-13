"""Task 9 — Prometheus metrics endpoint.

GET /api/metrics must return Prometheus text-format output containing
at least the http_requests_total counter.
"""
from fastapi.testclient import TestClient

from main import app


def test_metrics_endpoint_exposes_request_counter():
    client = TestClient(app)

    # Make a few requests to populate counters
    client.get("/api/health")
    client.get("/api/health")

    r = client.get("/api/metrics")
    assert r.status_code == 200
    body = r.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body


def test_metrics_includes_external_api_counters():
    client = TestClient(app)
    r = client.get("/api/metrics")
    assert r.status_code == 200
    body = r.text
    # Counter families should be declared even if no calls made yet
    assert "external_api_calls_total" in body
