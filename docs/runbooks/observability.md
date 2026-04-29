# Observability Runbook

## Structured Logging

The application uses **structlog** for JSON-formatted structured logs. Every log line includes:

| Field         | Source                          |
|---------------|---------------------------------|
| `timestamp`   | ISO 8601 UTC                    |
| `level`       | info / warning / error          |
| `logger_name` | Python module path              |
| `request_id`  | From `X-Request-Id` header or auto-generated UUID |
| `event`       | Log message                     |

### Configuration

- Set `LOG_FORMAT=console` env var for human-readable dev output
- Default is JSON (production-ready for log aggregators)
- Logging is initialized at module load in `main.py` via `setup_logging()`

### Log Search Examples

```bash
# Find all errors in the last hour
cat app.log | jq 'select(.level == "error")'

# Trace a specific request
cat app.log | jq 'select(.request_id == "abc123")'

# Find slow external API calls
cat app.log | jq 'select(.event | contains("timeout"))'
```

## Prometheus Metrics

Metrics are exposed at `GET /api/metrics` in Prometheus text format.

### Available Metrics

#### HTTP Request Metrics
- `http_requests_total{method, path, status}` — request counter
- `http_request_duration_seconds{method, path}` — latency histogram

#### External API Metrics
- `external_api_calls_total{service, status}` — calls to che300/qwen
- `external_api_duration_seconds{service}` — external call latency

#### Job Metrics
- `jobs_total{job_type, status}` — dispatched job outcomes

### Scrape Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'auto-finance'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/metrics'
```

### Key Dashboards

1. **Request Rate & Latency** — `rate(http_requests_total[5m])` and `histogram_quantile(0.95, http_request_duration_seconds_bucket)`
2. **External API Health** — `rate(external_api_calls_total{status="error"}[5m])` by service
3. **Job Success Rate** — `rate(jobs_total{status="succeeded"}[5m]) / rate(jobs_total[5m])`

### Alert Rules (recommended)

```yaml
groups:
  - name: auto-finance
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
      - alert: ExternalAPIDown
        expr: rate(external_api_calls_total{status="error"}[5m]) > 0.5
        for: 10m
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 5
        for: 5m
```

## Request Tracing

Every request gets a unique `request_id` via `RequestContextMiddleware`:

1. Incoming `X-Request-Id` header is honoured (for upstream proxy correlation)
2. Otherwise a UUID is auto-generated
3. The ID is returned in the `X-Request-Id` response header
4. The ID is stored in `request.state.request_id` for audit logs

To trace a request end-to-end: search logs and audit_logs table by `request_id`.
