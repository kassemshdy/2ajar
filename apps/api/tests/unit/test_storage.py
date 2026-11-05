import io
from pathlib import Path
from typing import Any

import pytest
from botocore.exceptions import ClientError
from botocore.response import StreamingBody

from app.core.config import Settings
from app.storage import LocalStorage, MediaNotFound, S3Storage, media_url, validate_key


@pytest.mark.parametrize("key", ["", "/etc/passwd", "a/../b", "../x", "a//b", "a\\b", "./a"])
def test_invalid_keys(key: str) -> None:
    with pytest.raises(ValueError):
        validate_key(key)


def test_media_url() -> None:
    assert media_url("listings/x/y.webp") == "/media/listings/x/y.webp"


async def test_local_roundtrip(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    await store.put("a/b.webp", b"img", "image/webp")
    assert await store.get("a/b.webp") == (b"img", "image/webp")
    await store.put("a/c.bin", b"x", "application/octet-stream")
    assert (await store.get("a/c.bin"))[1] == "application/octet-stream"
    await store.delete("a/b.webp")
    with pytest.raises(MediaNotFound):
        await store.get("a/b.webp")
    await store.delete("a/b.webp")  # idempotent


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.fail_with: str | None = None

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:
        assert Bucket == "media"
        self.objects[Key] = (Body, ContentType)

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if self.fail_with or Key not in self.objects:
            code = self.fail_with or "NoSuchKey"
            raise ClientError({"Error": {"Code": code, "Message": code}}, "GetObject")
        body, ctype = self.objects[Key]
        return {"Body": StreamingBody(io.BytesIO(body), len(body)), "ContentType": ctype}

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.objects.pop(Key, None)


async def test_s3_roundtrip_and_errors() -> None:
    fake = FakeS3()
    store = S3Storage(Settings(storage_backend="s3", s3_bucket="media"), client=fake)
    await store.put("k/1.webp", b"data", "image/webp")
    assert await store.get("k/1.webp") == (b"data", "image/webp")
    await store.delete("k/1.webp")
    with pytest.raises(MediaNotFound):
        await store.get("k/1.webp")
    fake.objects["k/2"] = (b"x", "")
    assert (await store.get("k/2"))[1] == "application/octet-stream"
    fake.fail_with = "AccessDenied"
    with pytest.raises(ClientError):
        await store.get("k/2")


def test_s3_requires_bucket_and_builds_boto_client() -> None:
    with pytest.raises(RuntimeError):
        S3Storage(Settings(storage_backend="s3"))
    store = S3Storage(
        Settings(
            storage_backend="s3",
            s3_bucket="b",
            s3_endpoint_url="https://s3.example.com",
            s3_access_key_id="k",
            s3_secret_access_key="s",
            s3_region="auto",
        )
    )
    assert store.client.meta.endpoint_url == "https://s3.example.com"
