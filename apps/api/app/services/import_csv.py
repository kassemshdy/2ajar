"""Bulk import of a publisher's own listings from CSV. Rows become drafts; photos are added afterwards."""

import csv
import io
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.policies import Principal, can_create_listing
from app.core.errors import Forbidden, PayloadTooLarge, ValidationFailed
from app.core.events import EventRecorder
from app.domain.events import ListingsImported
from app.repositories.locations import LocationDirectory
from app.schemas.listing import ListingCreate
from app.services.audit import AuditTrail
from app.services.listings import ListingService, normalize_whatsapp

MAX_BYTES = 1024 * 1024
MAX_ROWS = 200

COLUMNS = [
    "transaction_type",
    "property_type",
    "location",
    "price_usd",
    "price_period",
    "bedrooms",
    "bathrooms",
    "area_sqm",
    "floor",
    "max_guests",
    "furnished",
    "amenities",
    "title_en",
    "title_ar",
    "description_en",
    "description_ar",
    "contact_whatsapp",
]
# transaction_type is optional and defaults to "rent" (2ajar is rentals only; "sale" rows are rejected).
REQUIRED = {"property_type", "location", "price_usd"}
INT_FIELDS = {"price_usd", "bedrooms", "bathrooms", "area_sqm", "floor", "max_guests"}

TEMPLATE_EXAMPLE = {
    "transaction_type": "rent",
    "property_type": "apartment",
    "location": "achrafieh",
    "price_usd": "1200",
    "price_period": "monthly",
    "bedrooms": "2",
    "bathrooms": "2",
    "area_sqm": "140",
    "floor": "4",
    "max_guests": "",
    "furnished": "furnished",
    "amenities": "generator_24_7;parking;elevator",
    "title_en": "Bright 2-bedroom apartment in Achrafieh",
    "title_ar": "شقة مشرقة من غرفتي نوم في الأشرفية",
    "description_en": "Close to Sassine square.",
    "description_ar": "قريبة من ساحة ساسين.",
    "contact_whatsapp": "+961 70 123 456",
}


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


class ListingImporter:
    """Validate a CSV of listings and stage them as drafts in one transaction.

    The flow is a fixed pipeline (parse -> map rows -> validate -> persist), and every row is validated with
    the same ``ListingCreate`` schema and ``ListingService.add_draft`` used by the single-listing endpoint,
    so the importer can never accept data the regular form would reject.
    """

    def __init__(self, session: AsyncSession, *, listings: ListingService, events: EventRecorder) -> None:
        self._session = session
        self._listings = listings
        self._locations: LocationDirectory = listings.locations
        self._events = events
        self._audit = AuditTrail(session)

    async def run(
        self, p: Principal, raw: bytes, *, dry_run: bool, actor_name: str, request: Request | None = None
    ) -> list[RowResult]:
        if not can_create_listing(p):
            raise Forbidden("Only owners and brokers can import listings")
        rows = self._parse(raw)
        results: list[RowResult] = []
        valid: list[tuple[RowResult, ListingCreate]] = []
        for number, row in enumerate(rows, start=2):  # row 1 is the header
            result, data = await self._validate_row(number, row)
            results.append(result)
            if data is not None:
                valid.append((result, data))

        if dry_run or not valid:
            return results
        for result, data in valid:
            listing = await self._listings.add_draft(p, data)
            result.listing_id = str(listing.id)
        self._audit.record(
            p.user_id,
            "listing.import",
            "listing",
            None,
            request=request,
            data={"created": len(valid), "rows": len(rows)},
        )
        await self._session.commit()
        self._events.record(ListingsImported(created=len(valid), actor_name=actor_name))
        return results

    @staticmethod
    def _parse(raw: bytes) -> list[dict[str, str]]:
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
        return rows

    async def _validate_row(self, number: int, row: dict[str, str]) -> tuple[RowResult, ListingCreate | None]:
        payload, errors = await self._to_payload(row)
        result = RowResult(row=number, ok=False, title=payload.get("title_en") or payload.get("title_ar"))
        data: ListingCreate | None = None
        if not errors:
            try:
                data = ListingCreate.model_validate(payload)
                normalize_whatsapp(data.contact_whatsapp)
            except ValidationError as exc:
                errors = [f"{'.'.join(str(x) for x in e['loc']) or 'row'}: {e['msg']}" for e in exc.errors()]
                data = None
            except ValidationFailed as exc:
                errors = [exc.message]
                data = None
        result.errors = errors
        result.ok = not errors
        return result, data

    async def _to_payload(self, row: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
        errors: list[str] = []
        values = {k: (row.get(k) or "").strip() for k in COLUMNS}
        errors.extend(f"{col} is required" for col in sorted(REQUIRED) if not values[col])
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
            location = await self._locations.resolve(values["location"])  # cached lookup by slug/EN/AR name
            if location is None:
                errors.append(f"Unknown location '{values['location']}'")
            else:
                payload["location_id"] = location.id
        payload.setdefault("transaction_type", "rent")
        payload.setdefault("price_period", "monthly")
        return payload, errors
