"""Object storage abstraction. Local filesystem for development, S3-compatible for deployed envs."""

import asyncio
from pathlib import Path
from typing import Any, Protocol

from app.core.config import Settings, get_settings


class StorageBackend(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def delete(self, key: str) -> None: ...
    def url(self, key: str) -> str: ...


class LocalStorage:
    def __init__(self, root: Path, url_prefix: str) -> None:
        self.root = root.resolve()
        self.url_prefix = url_prefix.rstrip("/")

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("invalid storage key")
        return path

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)

    async def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def url(self, key: str) -> str:
        return f"{self.url_prefix}/{key}"


class S3Storage:
    def __init__(self, s: Settings) -> None:
        import boto3  # imported lazily so local dev/tests don't need credentials

        if not (s.s3_bucket and s.s3_public_base_url):
            raise RuntimeError("S3_BUCKET and S3_PUBLIC_BASE_URL are required for STORAGE_BACKEND=s3")
        self.bucket = s.s3_bucket
        self.public_base = s.s3_public_base_url.rstrip("/")
        self.client: Any = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint_url,
            aws_access_key_id=s.s3_access_key_id,
            aws_secret_access_key=s.s3_secret_access_key,
            region_name=s.s3_region,
        )

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)

    def url(self, key: str) -> str:
        return f"{self.public_base}/{key}"


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        s = get_settings()
        _storage = (
            S3Storage(s) if s.storage_backend == "s3" else LocalStorage(s.media_root, s.media_url_prefix)
        )
    return _storage
