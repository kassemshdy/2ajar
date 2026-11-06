"""Object storage: local filesystem in development, S3-compatible (e.g. a Railway bucket) when deployed.

Media is always served by the API at `/media/{key}` (proxied by the web app), so buckets stay private.
"""

import asyncio
from pathlib import Path
from typing import Any, Protocol

from app.core.config import Settings, get_settings

MEDIA_PREFIX = "/media"


class MediaNotFound(Exception):
    pass


def validate_key(key: str) -> str:
    parts = key.split("/")
    if not key or key.startswith("/") or any(p in ("", ".", "..") for p in parts) or "\\" in key:
        raise ValueError("invalid storage key")
    return key


class StorageBackend(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def get(self, key: str) -> tuple[bytes, str]: ...
    async def delete(self, key: str) -> None: ...


def media_url(key: str) -> str:
    return f"{MEDIA_PREFIX}/{key}"


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / validate_key(key)).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("invalid storage key")
        return path

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)

    async def get(self, key: str) -> tuple[bytes, str]:
        path = self._path(key)
        if not path.is_file():
            raise MediaNotFound(key)
        content_type = "image/webp" if path.suffix == ".webp" else "application/octet-stream"
        return await asyncio.to_thread(path.read_bytes), content_type

    async def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage:
    def __init__(self, s: Settings, client: Any = None) -> None:
        if not s.s3_bucket:
            raise RuntimeError("S3_BUCKET is required for STORAGE_BACKEND=s3")
        self.bucket = s.s3_bucket
        if client is None:
            import boto3  # imported lazily so local dev/tests don't need credentials

            client = boto3.client(
                "s3",
                endpoint_url=s.s3_endpoint_url,
                aws_access_key_id=s.s3_access_key_id,
                aws_secret_access_key=s.s3_secret_access_key,
                region_name=s.s3_region,
            )
        self.client = client

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=validate_key(key),
            Body=data,
            ContentType=content_type,
        )

    async def get(self, key: str) -> tuple[bytes, str]:
        from botocore.exceptions import ClientError

        try:
            obj = await asyncio.to_thread(self.client.get_object, Bucket=self.bucket, Key=validate_key(key))
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404", "NotFound"):
                raise MediaNotFound(key) from exc
            raise
        body = await asyncio.to_thread(obj["Body"].read)
        return body, str(obj.get("ContentType") or "application/octet-stream")

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=validate_key(key))


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        s = get_settings()
        _storage = S3Storage(s) if s.storage_backend == "s3" else LocalStorage(s.media_root)
    return _storage
