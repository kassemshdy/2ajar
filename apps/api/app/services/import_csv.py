"""Bulk import of a publisher's own listings from CSV. Rows become drafts; photos are added afterwards."""

import csv
import io
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.policies import Principal, can_create_listing
from app.core.errors import Forbidden, PayloadTooLarge, ValidationFailed
from app.models import Location
from app.schemas.listing import ListingCreate
from app.services.audit import audit
from app.services.listings import _normalize_whatsapp, add_listing

MAX_BYTES = 1024 * 1024
MAX_ROWS = 200

COLUMNS = [
    "transaction_type", "property_type", "location", "price_usd", "price_period", "bedrooms", "bathrooms",
    "area_sqm", "floor", "furnished", "amenities", "title_en", "title_ar", "description_en", "description_ar",
    "contact_whatsapp",
]  # fmt: skip
REQUIRED = {"transaction_type", "property_type", "location", "price_usd"}
INT_FIELDS = {"price_usd", "bedrooms", "bathrooms", "area_sqm", "floor"}

TEMPLATE_EXAMPLE = {
    "transaction_type": "rent", "property_type": "apartment", "location": "achrafieh", "price_usd": "1200",
    "price_period": "monthly", "bedrooms": "2", "bathrooms": "2", "area_sqm": "140", "floor": "4",
    "furnished": "furnished", "amenities": "generator_24_7;parking;elevator",
    "title_en": "Bright 2-bedroom apartment in Achrafieh", "title_ar": "شقة مشرقة من غرفتي نوم في الأشرفية",
    "description_en": "Close to Sassine square.", "description_ar": "قريبة من ساحة ساسين.",
    "contact_whatsapp": "+961 70 123 456",
}  # fmt: skip


def template_csv() -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerow(TEMPLATE_EXAMPLE)
    return out.getvalue()


@dataclass
class RowResult:
    row: int
    ok: bool
    listing_id: str | None = None
    title: str | None = None
    errors: list[str] = field(default_factory=list)


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1256"):  # Excel on Arabic Windows often saves cp1256
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValidationFailed("CSV must be UTF-8 encoded")


async def _location_index(session: AsyncSession) -> dict[str, Location]:
    index: dict[str, Location] = {}
    for loc in (await session.scalars(select(Location))).all():
        for key in (loc.slug, loc.name_en.lower(), loc.name_ar):
            index.setdefault(key.strip(), loc)
    return index


def _row_to_payload(row: dict[str, str], locations: dict[str, Location]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    values = {k: (row.get(k) or "").strip() for k in COLUMNS}
    for col in sorted(REQUIRED):
        if not values[col]:
            errors.append(f"{col} is required")
    payload: dict[str, Any] = {}
    for key, value in values.items():
        if not value or key == "location":
            continue
        if key in INT_FIELDS:
            try:
                payload[key] = int(value.replace(",", ""))
            except ValueError:
                errors.append(f"{key} must be a whole number")
        elif key == "amenities":
            payload[key] = [a.strip() for a in value.split(";") if a.strip()]
        else:
            payload[key] = value
    if values["location"]:
        loc = locations.get(values["location"]) or locations.get(values["location"].lower())
        if loc is None:
            errors.append(f"Unknown location '{values['location']}'")
        else:
            payload["location_id"] = loc.id
    if "price_period" not in payload:
        payload["price_period"] = "total" if values["transaction_type"] == "sale" else "monthly"
    return payload, errors


async def import_listings(
    session: AsyncSession, p: Principal, raw: bytes, *, dry_run: bool, request: Request
) -> list[RowResult]:
    if not can_create_listing(p):
        raise Forbidden("Only owners and brokers can import listings")
    if len(raw) > MAX_BYTES:
        raise PayloadTooLarge("CSV files must be at most 1 MB")
    reader = csv.DictReader(io.StringIO(_decode(raw)))
    header = [h.strip() for h in (reader.fieldnames or [])]
    missing = REQUIRED - set(header)
    if missing:
        raise ValidationFailed(f"Missing columns: {', '.join(sorted(missing))}", details=sorted(missing))
    reader.fieldnames = header
    rows = list(reader)
    if not rows:
        raise ValidationFailed("The CSV file has no data rows")
    if len(rows) > MAX_ROWS:
        raise ValidationFailed(f"At most {MAX_ROWS} rows per import")

    locations = await _location_index(session)
    results: list[RowResult] = []
    valid: list[tuple[RowResult, ListingCreate]] = []
    for i, row in enumerate(rows, start=2):  # row 1 is the header
        payload, errors = _row_to_payload(row, locations)
        result = RowResult(row=i, ok=False, title=payload.get("title_en") or payload.get("title_ar"))
        data: ListingCreate | None = None
        if not errors:
            try:
                data = ListingCreate.model_validate(payload)
                _normalize_whatsapp(data.contact_whatsapp)
            except ValidationError as exc:
                errors = [f"{'.'.join(str(x) for x in e['loc']) or 'row'}: {e['msg']}" for e in exc.errors()]
            except ValidationFailed as exc:
                errors = [exc.message]
        result.errors = errors
        result.ok = not errors
        results.append(result)
        if data is not None and not errors:
            valid.append((result, data))

    if dry_run or not valid:
        return results
    for result, data in valid:
        listing = await add_listing(session, p, data)
        result.listing_id = str(listing.id)
    audit(
        session,
        actor_id=p.user_id,
        action="listing.import",
        resource_type="listing",
        resource_id=None,
        data={"created": len(valid), "rows": len(rows)},
        request=request,
    )
    await session.commit()
    return results
