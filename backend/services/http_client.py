"""Resilient HTTP client — timeout, retry with exponential backoff, and
domain-specific error wrapping for external API calls.

Usage::

    from services.http_client import resilient_post, resilient_get

    data = await resilient_post(
        "che300",
        url,
        data=payload,
        headers=headers,
        timeout=10,
        retries=2,
    )
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

import httpx

from services.metrics import EXTERNAL_API_CALLS, EXTERNAL_API_LATENCY

logger = logging.getLogger(__name__)


# ---------- Domain errors ----------

class ExternalServiceError(Exception):
    """A remote service returned a non-success response after all retries."""

    def __init__(
        self,
        service: str,
        url: str,
        status_code: int = 0,
        message: str = "",
    ):
        self.service = service
        self.url = url
        self.status_code = status_code
        super().__init__(
            f"[{service}] {url} → {status_code}: {message}"
        )


class ExternalTimeoutError(ExternalServiceError):
    """A remote service did not respond within the timeout."""

    def __init__(self, service: str, url: str):
        super().__init__(service=service, url=url, status_code=0, message="timeout")


# ---------- Internal helpers ----------

_RETRYABLE_STATUS = {502, 503, 504, 429}


async def _attempt(
    method: str,
    service: str,
    url: str,
    *,
    timeout: float,
    retries: int,
    **kwargs: Any,
) -> httpx.Response:
    last_exc: Optional[Exception] = None

    for attempt in range(1 + retries):
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await getattr(client, method)(url, **kwargs)

            elapsed = time.monotonic() - start
            EXTERNAL_API_LATENCY.labels(service=service).observe(elapsed)

            if resp.status_code < 400:
                EXTERNAL_API_CALLS.labels(service=service, status="success").inc()
                return resp

            if resp.status_code in _RETRYABLE_STATUS and attempt < retries:
                EXTERNAL_API_CALLS.labels(service=service, status="retry").inc()
                wait = min(2 ** attempt * 0.5, 8)
                logger.warning(
                    "retrying %s %s (status=%d, attempt=%d)",
                    method.upper(), url, resp.status_code, attempt + 1,
                )
                await asyncio.sleep(wait)
                continue

            EXTERNAL_API_CALLS.labels(service=service, status="error").inc()
            raise ExternalServiceError(
                service=service,
                url=url,
                status_code=resp.status_code,
                message=resp.text[:200],
            )

        except httpx.TimeoutException:
            elapsed = time.monotonic() - start
            EXTERNAL_API_LATENCY.labels(service=service).observe(elapsed)
            EXTERNAL_API_CALLS.labels(service=service, status="timeout").inc()
            last_exc = ExternalTimeoutError(service=service, url=url)
            if attempt < retries:
                logger.warning(
                    "timeout %s %s (attempt=%d)", method.upper(), url, attempt + 1
                )
                await asyncio.sleep(min(2 ** attempt * 0.5, 8))
                continue
            raise last_exc

        except ExternalServiceError:
            raise

        except Exception as exc:
            elapsed = time.monotonic() - start
            EXTERNAL_API_LATENCY.labels(service=service).observe(elapsed)
            EXTERNAL_API_CALLS.labels(service=service, status="error").inc()
            last_exc = exc
            if attempt < retries:
                await asyncio.sleep(min(2 ** attempt * 0.5, 8))
                continue
            raise ExternalServiceError(
                service=service, url=url, status_code=0, message=str(exc)
            ) from exc

    # Should not reach here, but just in case
    raise last_exc  # type: ignore[misc]


# ---------- Public API ----------

async def resilient_post(
    service: str,
    url: str,
    *,
    timeout: float = 15,
    retries: int = 2,
    **kwargs: Any,
) -> httpx.Response:
    """POST with retry + timeout + error wrapping."""
    return await _attempt("post", service, url, timeout=timeout, retries=retries, **kwargs)


async def resilient_get(
    service: str,
    url: str,
    *,
    timeout: float = 15,
    retries: int = 2,
    **kwargs: Any,
) -> httpx.Response:
    """GET with retry + timeout + error wrapping."""
    return await _attempt("get", service, url, timeout=timeout, retries=retries, **kwargs)
