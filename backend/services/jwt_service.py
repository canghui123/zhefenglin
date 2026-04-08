"""Minimal HS256 JWT helper.

We avoid pulling in PyJWT for now — the auth flow only needs encode +
decode + signature/expiry verification. If we later need RS256, refresh
tokens with rotation, or JWKS, swap the implementation for PyJWT and keep
the public surface (`encode`, `decode`, `JWTError`).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from config import settings


class JWTError(Exception):
    """Raised when a JWT is malformed, expired, or has a bad signature."""


_ALG_HEADER = {"alg": "HS256", "typ": "JWT"}
_DEFAULT_ACCESS_TTL = timedelta(hours=12)


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(message: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64encode(sig)


def encode_access_token(
    *,
    user_id: int,
    email: str,
    role: str,
    jti: str,
    ttl: Optional[timedelta] = None,
    secret: Optional[str] = None,
) -> str:
    """Build a signed access token. Returns the compact JWT string."""
    now = datetime.now(timezone.utc)
    exp = now + (ttl or _DEFAULT_ACCESS_TTL)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    secret = secret or settings.jwt_secret
    header_b64 = _b64encode(json.dumps(_ALG_HEADER, separators=(",", ":")).encode())
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig_b64 = _sign(signing_input, secret)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def access_token_expiry(ttl: Optional[timedelta] = None) -> datetime:
    return datetime.now(timezone.utc) + (ttl or _DEFAULT_ACCESS_TTL)


def decode_access_token(token: str, *, secret: Optional[str] = None) -> Dict[str, Any]:
    """Verify the signature + expiry and return the payload as a dict.

    Raises JWTError on any validation failure.
    """
    if not token or not isinstance(token, str):
        raise JWTError("missing token")
    parts = token.split(".")
    if len(parts) != 3:
        raise JWTError("malformed token")

    header_b64, payload_b64, sig_b64 = parts
    secret = secret or settings.jwt_secret

    expected_sig = _sign(f"{header_b64}.{payload_b64}".encode("ascii"), secret)
    if not hmac.compare_digest(expected_sig, sig_b64):
        raise JWTError("bad signature")

    try:
        payload = json.loads(_b64decode(payload_b64).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise JWTError("bad payload") from exc

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise JWTError("missing exp claim")
    if datetime.now(timezone.utc).timestamp() > exp:
        raise JWTError("token expired")

    return payload
