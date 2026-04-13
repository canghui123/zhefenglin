"""Middleware that records HTTP request count and latency for Prometheus."""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from services.metrics import HTTP_REQUESTS, HTTP_LATENCY


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Normalise path to avoid cardinality explosion on path params
        path = request.url.path
        method = request.method

        start = time.monotonic()
        response: Response = await call_next(request)
        elapsed = time.monotonic() - start

        # Collapse dynamic path segments to reduce label cardinality
        normalised = _normalise_path(path)

        HTTP_REQUESTS.labels(
            method=method,
            path=normalised,
            status=response.status_code,
        ).inc()
        HTTP_LATENCY.labels(method=method, path=normalised).observe(elapsed)

        return response


def _normalise_path(path: str) -> str:
    """Replace numeric path segments with {id} to keep cardinality bounded."""
    parts = path.split("/")
    out = []
    for p in parts:
        if p.isdigit():
            out.append("{id}")
        else:
            out.append(p)
    return "/".join(out)
