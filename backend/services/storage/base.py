"""Abstract storage interface.

Every storage back-end (local filesystem, S3/MinIO) implements this
protocol. Callers always go through `factory.get_storage()` so the
back-end can be swapped via `config.settings.storage_backend` without
touching any business code.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Optional


@dataclass
class StoredObject:
    """Lightweight receipt returned after a successful write."""
    key: str
    size: int
    content_type: str


class StorageBackend(abc.ABC):
    """Minimal object-storage contract."""

    @abc.abstractmethod
    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredObject:
        ...

    @abc.abstractmethod
    def get_bytes(self, key: str) -> bytes:
        ...

    @abc.abstractmethod
    def delete_object(self, key: str) -> None:
        ...

    @abc.abstractmethod
    def build_download_url(self, key: str, expires_in: int = 300) -> Optional[str]:
        """Return a pre-signed URL (S3) or ``None`` (local — caller must
        proxy the download)."""
        ...
