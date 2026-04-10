"""Singleton factory for the configured storage back-end.

Usage::

    from services.storage.factory import get_storage
    store = get_storage()
    store.put_bytes("uploads/pkg_42.xlsx", data)
"""
from __future__ import annotations

from typing import Optional

from config import settings
from services.storage.base import StorageBackend

_instance: Optional[StorageBackend] = None


def get_storage() -> StorageBackend:
    global _instance
    if _instance is not None:
        return _instance

    if settings.storage_backend == "s3":
        from services.storage.s3 import S3Storage
        _instance = S3Storage()
    else:
        from services.storage.local import LocalStorage
        _instance = LocalStorage()

    return _instance


def reset_storage() -> None:
    """Drop the cached singleton — used by tests that swap upload_dir."""
    global _instance
    _instance = None
