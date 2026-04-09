"""Per-request context middleware.

Stamps every incoming HTTP request with a unique `request_id` and exposes
the client IP / user-agent on `request.state` so downstream code (audit
service, error handlers, log formatters) can read them without re-parsing
the headers.

Clients may pre-supply an `X-Request-Id` header (e.g. an upstream proxy
or load balancer); we honour it when present so a single request can be
correlated end-to-end.
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


REQUEST_ID_HEADER = "X-Request-Id"


def _short_id() -> str:
    return uuid.uuid4().hex


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming.strip() if incoming else _short_id()

        request.state.request_id = request_id
        request.state.client_ip = request.client.host if request.client else None
        request.state.user_agent = request.headers.get("user-agent")

        response: Response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
