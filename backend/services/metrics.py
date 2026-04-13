"""Prometheus metrics — counters and histograms used across the app.

Import the metric objects you need; they are registered in the default
prometheus_client registry and exposed by ``GET /api/metrics``.
"""
from prometheus_client import Counter, Histogram

# ---- HTTP request metrics (populated by middleware) ----

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# ---- External API metrics (populated by http_client / LLM wrappers) ----

EXTERNAL_API_CALLS = Counter(
    "external_api_calls_total",
    "Calls to external APIs",
    ["service", "status"],
)

EXTERNAL_API_LATENCY = Histogram(
    "external_api_duration_seconds",
    "External API call latency in seconds",
    ["service"],
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)

# ---- Job metrics ----

JOBS_TOTAL = Counter(
    "jobs_total",
    "Total dispatched jobs",
    ["job_type", "status"],
)
