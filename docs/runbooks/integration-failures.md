# Integration Failure Runbook

## Overview

The platform depends on two external services:

| Service   | Purpose         | Endpoint                              | Timeout | Retries |
|-----------|-----------------|---------------------------------------|---------|---------|
| che300    | VIN car pricing | `cloud-api.che300.com`                | 15 s    | 2       |
| Qwen      | LLM inference   | `dashscope.aliyuncs.com`              | 30 s    | 0       |

Both are wrapped in resilient clients (`services/http_client.py` and `services/llm_client.py`) that translate failures into domain errors.

## Alerts

Monitor the following Prometheus metrics at `/api/metrics`:

- `external_api_calls_total{service="che300",status="error"}` — rising count means che300 is failing
- `external_api_calls_total{service="che300",status="timeout"}` — rising count means che300 is slow
- `external_api_calls_total{service="qwen",status="error"}` — Qwen/DashScope failures
- `external_api_duration_seconds` — latency histogram per service

## che300 Failures

**Symptoms:** Asset package calculations return mock valuations; `ExternalServiceError` or `ExternalTimeoutError` in logs.

**Diagnosis:**
1. Check `external_api_calls_total{service="che300",status!="success"}` in metrics
2. Search structured logs for `service=che300`
3. Verify API credentials in `.env`: `CHE300_ACCESS_KEY`, `CHE300_ACCESS_SECRET`
4. Test connectivity: `curl -s https://cloud-api.che300.com/open/v1/get-eval-price-by-vin`
5. Use a real VIN from customer data for an end-to-end valuation smoke test:

```bash
cd /opt/app/deploy
sudo docker compose exec backend python3 - <<'PY'
import asyncio
import os
from db.session import get_db_session
from services.che300_client import get_valuation_by_vin

VIN = os.environ.get("CHE300_TEST_VIN", "请替换成真实VIN")

async def main():
    gen = get_db_session()
    session = next(gen)
    try:
        result = await get_valuation_by_vin(
            session,
            VIN,
            city_name=os.environ.get("DEFAULT_CITY_NAME", "南京"),
            reg_date="2021-01-01",
            mile_age=5,
        )
        print(result.model_dump())
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

asyncio.run(main())
PY
```

**Mitigation:**
- The system falls back to mock valuations automatically when che300 is unavailable
- No user action is needed for continued operation
- Calculations completed with mock data can be re-run once che300 recovers

**Escalation:** Contact che300 support if errors persist > 30 minutes.

## Qwen / DashScope Failures

**Symptoms:** Depreciation predictions use default rates; LLM responses show `[LLM调用失败]` placeholder.

**Diagnosis:**
1. Check `external_api_calls_total{service="qwen",status="error"}` in metrics
2. Verify API key in `.env`: `QWEN_API_KEY` or `DASHSCOPE_API_KEY`
3. Verify base URL: `QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
4. Run a minimal OpenAI-compatible chat-completions request from the backend container

```bash
cd /opt/app/deploy
sudo docker compose exec backend python3 - <<'PY'
import asyncio
from services.llm_client import chat_completion, get_llm_runtime_config

async def main():
    cfg = get_llm_runtime_config()
    print(
        "runtime:",
        None
        if cfg is None
        else {
            "service": cfg.service,
            "base_url": cfg.base_url,
            "model": cfg.model,
            "api_key": "SET" if cfg.api_key else "EMPTY",
        },
    )
    print(await chat_completion("你是健康检查助手，只回答OK。", "请只返回 OK", max_tokens=20))

asyncio.run(main())
PY
```

**Mitigation:**
- The depreciation service falls back to conservative age-based defaults
- Report generation uses template-only output without AI commentary
- No data loss occurs

**Escalation:** Check Alibaba Cloud DashScope status / quota, then rotate key or switch `LLM_PROVIDER`.

## General Resilience Patterns

The `resilient_post` / `resilient_get` functions in `services/http_client.py` provide:

1. **Configurable timeout** — per-call, prevents thread/connection exhaustion
2. **Exponential backoff retry** — on 502/503/504/429, up to `retries` attempts
3. **Domain error wrapping** — `ExternalTimeoutError`, `ExternalServiceError` with service name and status code
4. **Prometheus instrumentation** — every call records latency + outcome
