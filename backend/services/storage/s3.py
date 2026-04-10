"""S3-compatible (MinIO / AWS) storage back-end.

Requires ``boto3`` at runtime, which is only imported lazily so the rest
of the codebase can boot without it when ``storage_backend = "local"``.
"""
from __future__ import annotations

from typing import Optional

from config import settings
from services.storage.base import StorageBackend, StoredObject


class S3Storage(StorageBackend):
    def __init__(self) -> None:
        import boto3  # lazy — not needed for local dev

        kwargs = {
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
        }
        if settings.s3_endpoint:
            kwargs["endpoint_url"] = settings.s3_endpoint
        self._client = boto3.client("s3", **kwargs)
        self._bucket = settings.s3_bucket
        # Auto-create the bucket if MinIO returns 404
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except self._client.exceptions.ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredObject:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return StoredObject(key=key, size=len(data), content_type=content_type)

    def get_bytes(self, key: str) -> bytes:
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        return resp["Body"].read()

    def delete_object(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def build_download_url(self, key: str, expires_in: int = 300) -> Optional[str]:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )
