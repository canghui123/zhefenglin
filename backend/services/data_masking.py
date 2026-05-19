"""Data masking helpers for read-only exports and low-privilege views."""

from __future__ import annotations

from typing import Any


SENSITIVE_KEYWORDS = (
    "vin",
    "phone",
    "mobile",
    "id_card",
    "identity",
    "license_plate",
    "plate_number",
    "debtor_name",
    "customer_name",
)


def _mask_string(value: str) -> str:
    if not value:
        return value
    if len(value) <= 4:
        return "*" * len(value)
    if len(value) <= 8:
        return value[:1] + "*" * (len(value) - 2) + value[-1:]
    return value[:3] + "*" * (len(value) - 7) + value[-4:]


def mask_sensitive_payload(payload: Any) -> Any:
    """Recursively mask sensitive fields while preserving the JSON shape."""
    if isinstance(payload, list):
        return [mask_sensitive_payload(item) for item in payload]
    if isinstance(payload, dict):
        masked: dict[str, Any] = {}
        for key, value in payload.items():
            normalized = key.lower()
            if any(keyword in normalized for keyword in SENSITIVE_KEYWORDS):
                masked[key] = _mask_string(str(value)) if value is not None else None
            else:
                masked[key] = mask_sensitive_payload(value)
        return masked
    return payload
