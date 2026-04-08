"""Password hashing and verification.

Implementation: PBKDF2-HMAC-SHA256 from the stdlib. We deliberately avoid
pulling in `passlib`/`bcrypt` as a dependency for Task 5; the encoding is
forward-compatible — `verify_password` looks at the algorithm prefix so we
can introduce a stronger scheme later without breaking existing hashes.

Encoded format::

    pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 200_000
_SALT_BYTES = 16
_DK_LEN = 32


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(plain: str) -> str:
    if not isinstance(plain, str) or not plain:
        raise ValueError("password must be a non-empty string")
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt, _ITERATIONS, dklen=_DK_LEN
    )
    return f"{_ALGO}${_ITERATIONS}${_b64encode(salt)}${_b64encode(dk)}"


def verify_password(plain: str, encoded: str) -> bool:
    if not plain or not encoded:
        return False
    try:
        algo, iter_str, salt_b64, hash_b64 = encoded.split("$", 3)
    except ValueError:
        return False
    if algo != _ALGO:
        return False
    try:
        iterations = int(iter_str)
    except ValueError:
        return False
    salt = _b64decode(salt_b64)
    expected = _b64decode(hash_b64)
    candidate = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt, iterations, dklen=len(expected)
    )
    return hmac.compare_digest(candidate, expected)
