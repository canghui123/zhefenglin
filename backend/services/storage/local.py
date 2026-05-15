"""Local-filesystem storage back-end.

Files are stored under `config.settings.upload_dir` with the object key
as the file name. This is the default for development / single-server
deployments and is wire-compatible with the S3 back-end so tests can run
without any external dependencies.
"""
from __future__ import annotations

import os
from typing import Optional

from config import settings
from services.storage.base import StorageBackend, StoredObject


class LocalStorage(StorageBackend):
    def __init__(self, root_dir: Optional[str] = None) -> None:
        self._root = root_dir or settings.upload_dir
        os.makedirs(self._root, exist_ok=True)

    def _path(self, key: str) -> str:
        # 防路径穿越三重保险：
        # 1) key 不能含空字节、回车等异常字符
        if not key or "\x00" in key or "\r" in key or "\n" in key:
            raise ValueError("invalid storage key")
        # 2) 只取 basename，彻底剥离目录分量（../、绝对路径、盘符等）
        safe = os.path.basename(key)
        if not safe or safe in (".", ".."):
            raise ValueError("invalid storage key")
        full = os.path.join(self._root, safe)
        # 3) 规范化后必须仍在 root 内（防止符号链接/规范化异常）
        real_root = os.path.realpath(self._root)
        real_full = os.path.realpath(full)
        if not (real_full == real_root or real_full.startswith(real_root + os.sep)):
            raise ValueError("resolved path escapes storage root")
        return full

    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredObject:
        path = self._path(key)
        os.makedirs(os.path.dirname(path) or self._root, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return StoredObject(key=key, size=len(data), content_type=content_type)

    def get_bytes(self, key: str) -> bytes:
        path = self._path(key)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"storage key not found: {key}")
        with open(path, "rb") as f:
            return f.read()

    def delete_object(self, key: str) -> None:
        path = self._path(key)
        if os.path.isfile(path):
            os.remove(path)

    def build_download_url(self, key: str, expires_in: int = 300) -> Optional[str]:
        # Local storage cannot produce a URL; the API must proxy the bytes.
        return None
