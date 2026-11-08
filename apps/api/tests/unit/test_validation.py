import io
import uuid

import pytest
from PIL import Image
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ValidationFailed
from app.core.phone import normalize_phone
from app.core.security import password_problems
from app.schemas.lead import LeadCreate
from app.schemas.listing import ListingCreate, ListingUpdate
from app.services.images import process_image
from tests.conftest import jpeg_bytes


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+961 70 123 456", "+96170123456"),
        ("70123456", "+96170123456"),
        ("03 123 456", "+9613123456"),
        ("009613123456", "+9613123456"),
        ("+1 415 555 2671", "+14155552671"),
        ("123", None),
        ("not a phone", None),
        ("", None),
    ],
)
def test_normalize_phone(raw: str, expected: str | None) -> None:
    assert normalize_phone(raw) == expected


def test_password_policy() -> None:
    assert password_problems("short")
    assert password_problems("password123")
    assert not password_problems("a-long-unique-passphrase")


def _listing(**kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "transaction_type": "rent",
        "property_type": "apartment",
        "location_id": str(uuid.uuid4()),
        "price_usd": 900,
        "price_period": "monthly",
    }
    base.update(kw)
    return base


@pytest.mark.parametrize("period", ["hourly", "daily", "nightly", "weekly", "monthly", "yearly"])
def test_any_rental_period_is_accepted(period: str) -> None:
    created = ListingCreate.model_validate(_listing(price_period=period, max_guests=6))
    assert created.transaction_type == "rent" and created.max_guests == 6


def test_rentals_only() -> None:
    with pytest.raises(ValidationError, match="rentals only"):
        ListingCreate.model_validate(_listing(transaction_type="sale", price_period="total"))
    with pytest.raises(ValidationError, match="rental period"):
        ListingCreate.model_validate(_listing(price_period="total"))
    with pytest.raises(ValidationError, match="rentals only"):
        ListingUpdate.model_validate({"transaction_type": "sale"})
    assert "transaction_type" not in ListingCreate.model_validate(
        {k: v for k, v in _listing().items() if k != "transaction_type"}
    ).model_dump(exclude_defaults=True)
    with pytest.raises(ValidationError):
        ListingCreate.model_validate(_listing(max_guests=0))


@pytest.mark.parametrize("price", [0, -5, 100_000_001])
def test_listing_price_bounds(price: int) -> None:
    with pytest.raises(ValidationError):
        ListingCreate.model_validate(_listing(price_usd=price))


def test_listing_rejects_unknown_fields_and_amenities() -> None:
    with pytest.raises(ValidationError):
        ListingCreate.model_validate(_listing(status="published"))
    with pytest.raises(ValidationError):
        ListingCreate.model_validate(_listing(amenities=["helipad"]))


def test_lead_requires_explicit_consent() -> None:
    base = {"name": "Lea", "phone": "70123456", "consent_text_version": "v1"}
    LeadCreate.model_validate({**base, "consent": True})
    for bad in (False, None):
        with pytest.raises(ValidationError):
            LeadCreate.model_validate({**base, "consent": bad})
    with pytest.raises(ValidationError):
        LeadCreate.model_validate(base)


def test_production_guards() -> None:
    with pytest.raises(ValidationError):
        Settings(env="production", cookie_secure=True)  # default JWT secret
    with pytest.raises(ValidationError):
        Settings(env="production", jwt_secret="x" * 40, cookie_secure=True, demo_mode=True)
    with pytest.raises(ValidationError):
        Settings(env="staging", jwt_secret="x" * 40, cookie_secure=False)
    ok = Settings(env="production", jwt_secret="x" * 40, cookie_secure=True)
    assert ok.demo_mode is False


def test_database_url_normalization() -> None:
    s = Settings(database_url="postgres://u:p@h:5432/db")
    assert s.database_url == "postgresql+psycopg://u:p@h:5432/db"


# ---------- images ----------


def test_image_reencoded_to_webp_without_exif() -> None:
    raw = jpeg_bytes((3000, 2000))
    assert b"SecretCameraMaker" in raw
    out = process_image(raw)
    assert out.content_type == "image/webp"
    assert max(out.width, out.height) == 2048
    assert b"SecretCameraMaker" not in out.data
    with Image.open(io.BytesIO(out.data)) as img:
        assert img.format == "WEBP"
        assert not img.getexif()


def test_polyglot_payload_is_dropped() -> None:
    raw = jpeg_bytes() + b"<?php system($_GET['c']); ?>"
    out = process_image(raw)
    assert b"<?php" not in out.data


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"hello world, not an image",
        b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
        b"%PDF-1.4\n%...",
    ],
)
def test_non_images_rejected(raw: bytes) -> None:
    with pytest.raises(ValidationFailed):
        process_image(raw)


def test_gif_rejected() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (400, 400)).save(buf, format="GIF")
    with pytest.raises(ValidationFailed):
        process_image(buf.getvalue())


def test_too_small_rejected() -> None:
    with pytest.raises(ValidationFailed):
        process_image(jpeg_bytes((100, 100)))


def test_decompression_bomb_rejected() -> None:
    buf = io.BytesIO()
    Image.new("1", (12000, 12000)).save(buf, format="PNG")  # 144 MP, tiny file
    assert len(buf.getvalue()) < 1_000_000
    with pytest.raises(ValidationFailed):
        process_image(buf.getvalue())
