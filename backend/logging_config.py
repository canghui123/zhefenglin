"""Structured logging configuration using structlog.

Call ``setup_logging()`` once at app startup. After that, both
``structlog.get_logger()`` and stdlib ``logging.getLogger()`` produce
JSON-formatted output with bound context (request_id, tenant_id, etc.).
"""
from __future__ import annotations

import logging
import re
import sys

import structlog


# 字段名包含这些关键词的一律脱敏（大小写不敏感，按 endswith 匹配）
_SENSITIVE_KEY_PATTERNS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "access_key",
    "refresh_token",
    "session",
)

# 请求/响应 body 中常见的 JSON 键值掩码
_JSON_FIELD_RE = re.compile(
    r'("(?:password|passwd|token|access_token|refresh_token|secret|api_key|authorization)"\s*:\s*)"[^"]*"',
    re.IGNORECASE,
)

_REDACTED = "***REDACTED***"


def _should_redact_key(key: str) -> bool:
    k = key.lower()
    return any(pat in k for pat in _SENSITIVE_KEY_PATTERNS)


def _redact_value(value):
    if isinstance(value, str):
        return _JSON_FIELD_RE.sub(lambda m: m.group(1) + f'"{_REDACTED}"', value)
    if isinstance(value, dict):
        return {
            k: (_REDACTED if _should_redact_key(k) else _redact_value(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    return value


def _redact_processor(_logger, _name, event_dict):
    """structlog processor：对事件字典递归脱敏敏感字段。"""
    for key in list(event_dict.keys()):
        if _should_redact_key(key):
            event_dict[key] = _REDACTED
        else:
            event_dict[key] = _redact_value(event_dict[key])
    return event_dict


def setup_logging(*, json: bool = True, level: str = "INFO") -> None:
    """Configure structlog + stdlib logging for the application."""

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _redact_processor,
    ]

    if json:
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Quiet down noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
