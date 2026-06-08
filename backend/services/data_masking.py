"""Data masking helpers for audit logs, read-only exports, and low-privilege views.

Two complementary mechanisms:

1. **Field-name based** masking (legacy): if a JSON field name contains a
   sensitive keyword (`vin` / `phone` / `id_card` / ...), the entire value
   is masked irrespective of content.

2. **Value-content based** masking (B6, 2026-06-08): even when the field
   name is innocuous, scan the *string* value for VIN / 手机号 / 身份证 /
   邮箱 patterns and mask them in-place. This catches the case where
   audit log payloads or report draft sections embed raw PII inside
   prose text.

Both run by default. Pass `redact_text=False` if you only want the
legacy field-name pass (rare).
"""

from __future__ import annotations

import re
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


# ── value-content PII regexes ───────────────────────────────────────────
# VIN: 17 chars, no I/O/Q to avoid digit confusion. Word boundary so we
# don't slice into longer hex / hashes.
_VIN_RE = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b")

# Chinese mobile number: 1{3-9}########
_MOBILE_CN_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")

# Chinese national ID: 18 chars, last can be digit or X (case insensitive)
_ID_CARD_CN_RE = re.compile(r"(?<!\d)(\d{17}[\dXx])(?!\w)")

# Email: only `name@host.tld` style, minimal local + TLD so we don't
# eat `version@1.2.3` style version strings (TLD must be alpha)
_EMAIL_RE = re.compile(r"\b([\w.+-]+)@([\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,})\b")


def _mask_vin(match: "re.Match[str]") -> str:
    val = match.group(1)
    return val[:3] + "*" * (len(val) - 6) + val[-3:]


def _mask_mobile(match: "re.Match[str]") -> str:
    val = match.group(1)
    return val[:3] + "****" + val[-4:]


def _mask_id_card(match: "re.Match[str]") -> str:
    val = match.group(1)
    return val[:3] + "*" * 11 + val[-4:]


def _mask_email(match: "re.Match[str]") -> str:
    local, domain = match.group(1), match.group(2)
    if len(local) <= 1:
        return f"{local}***@{domain}"
    return f"{local[0]}***@{domain}"


def _redact_pii_in_text(text: str) -> str:
    """Identify and mask VIN / 手机号 / 身份证 / 邮箱 in free text."""
    text = _VIN_RE.sub(_mask_vin, text)
    text = _MOBILE_CN_RE.sub(_mask_mobile, text)
    text = _ID_CARD_CN_RE.sub(_mask_id_card, text)
    text = _EMAIL_RE.sub(_mask_email, text)
    return text


def _mask_string(value: str) -> str:
    if not value:
        return value
    if len(value) <= 4:
        return "*" * len(value)
    if len(value) <= 8:
        return value[:1] + "*" * (len(value) - 2) + value[-1:]
    return value[:3] + "*" * (len(value) - 7) + value[-4:]


def mask_sensitive_payload(payload: Any, *, redact_text: bool = True) -> Any:
    """Recursively mask sensitive fields while preserving the JSON shape.

    Args:
        payload: any JSON-serialisable structure
        redact_text: when True (default), string values are also scanned
            for VIN / 手机 / 身份证 / 邮箱 patterns and those substrings
            are masked. Set False to only run the legacy field-name pass.
    """
    if isinstance(payload, list):
        return [
            mask_sensitive_payload(item, redact_text=redact_text)
            for item in payload
        ]
    if isinstance(payload, dict):
        masked: dict[str, Any] = {}
        for key, value in payload.items():
            normalized = key.lower()
            if any(keyword in normalized for keyword in SENSITIVE_KEYWORDS):
                masked[key] = _mask_string(str(value)) if value is not None else None
            else:
                masked[key] = mask_sensitive_payload(value, redact_text=redact_text)
        return masked
    if isinstance(payload, str) and redact_text:
        return _redact_pii_in_text(payload)
    return payload
