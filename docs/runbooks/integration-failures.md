# Integration Failure Runbook

## Overview

The platform depends on two external services:

| Service   | Purpose         | Endpoint                              | Timeout | Retries |
|-----------|-----------------|---------------------------------------|---------|---------|
| che300    | VIN car pricing | `cloud-api.che300.com`                | 15 s    | 2       |
| DeepSeek  | LLM inference   | `api.deepseek.com`                    | 30 s    | 0       |

Both are wrapped in resilient clients (`services/http_client.py` and `services/llm_client.py`) that translate failures into domain errors.

## Alerts

Monitor the following Prometheus metrics at `/api/metrics`:

- `external_api_calls_total{service="che300",status="error"}` — rising count means che300 is failing
- `external_api_calls_total{service="che300",status="timeout"}` — rising count means che300 is slow
- `external_api_calls_total{service="deepseek",status="error"}` — DeepSeek failures
- `external_api_duration_seconds` — latency histogram per service

## che300 Failures

**Symptoms:** Asset package calculations return mock valuations; `ExternalServiceError` or `ExternalTimeoutError` in logs.

**Diagnosis:**
1. Check `external_api_calls_total{service="che300",status!="success"}` in metrics
2. Search structured logs for `service=che300`
3. Verify API credentials in `.env`: `CHE300_ACCESS_KEY`, `CHE300_ACCESS_SECRET`
4. Test connectivity: `curl -s https://cloud-api.che300.com/open/v1/get-eval-price-by-vin`

**Mitigation:**
- The system falls back to mock valuations automatically when che300 is unavailable
- No user action is needed for continued operation
- Calculations completed with mock data can be re-run once che300 recovers

**Escalation:** Contact che300 support if errors persist > 30 minutes.

## DeepSeek Failures

**Symptoms:** Depreciation predictions use default rates; LLM responses show `[LLM调用失败]` placeholder.

**Diagnosis:**
1. Check `external_api_calls_total{service="deepseek",status="error"}` in metrics
2. Verify API key in `.env`: `DEEPSEEK_API_KEY`
3. Check DeepSeek status page

**Mitigation:**
- The depreciation service falls back to conservative age-based defaults
- Report generation uses template-only output without AI commentary
- No data loss occurs

**Escalation:** Check DeepSeek status page or switch to alternative LLM provider.

## General Resilience Patterns

The `resilient_post` / `resilient_get` functions in `services/http_client.py` provide:

1. **Configurable timeout** — per-call, prevents thread/connection exhaustion
2. **Exponential backoff retry** — on 502/503/504/429, up to `retries` attempts
3. **Domain error wrapping** — `ExternalTimeoutError`, `ExternalServiceError` with service name and status code
4. **Prometheus instrumentation** — every call records latency + outcome
