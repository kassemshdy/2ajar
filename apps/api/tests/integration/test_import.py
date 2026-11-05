import csv
import io
from typing import Any

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import AuditLog, Listing
from app.services.import_csv import COLUMNS, TEMPLATE_EXAMPLE

URL = "/api/v1/listings/import"


def make_csv(rows: list[dict[str, str]], columns: list[str] = COLUMNS, encoding: str = "utf-8") -> bytes:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return out.getvalue().encode(encoding)


def row(**kw: str) -> dict[str, str]:
    return {**TEMPLATE_EXAMPLE, **kw}


async def post(actor: Any, data: bytes, dry_run: bool) -> Any:
    files = {"file": ("listings.csv", data, "text/csv")}
    return await actor.client.post(URL, params={"dry_run": str(dry_run).lower()}, files=files)


async def test_template_downloads(anon: Any) -> None:
    r = await anon.client.get(f"{URL}/template")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    parsed = list(csv.DictReader(io.StringIO(r.text)))
    assert parsed[0]["location"] == "achrafieh"


async def test_dry_run_then_import(make_actor: Any, notifications: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Agency")
    data = make_csv(
        [
            row(),
            row(location="Hamra", title_en="Hamra flat", price_usd="1,500"),
            row(
                location="الحمرا", title_en="", title_ar="شقة عربية", transaction_type="sale", price_period=""
            ),
            row(location="atlantis", title_en="Bad location"),
            row(price_usd="cheap", title_en="Bad price"),
            row(transaction_type="", title_en="Missing tx"),
            row(amenities="helipad", title_en="Bad amenity"),
            row(contact_whatsapp="12", title_en="Bad phone"),
        ]
    )
    r = await post(broker, data, dry_run=True)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dry_run"] is True and body["total"] == 8 and body["valid"] == 3 and body["created"] == 0
    rows = body["rows"]
    assert [x["row"] for x in rows] == list(range(2, 10))
    assert rows[3]["errors"] == ["Unknown location 'atlantis'"]
    assert "price_usd must be a whole number" in rows[4]["errors"]
    assert "transaction_type is required" in rows[5]["errors"]
    assert any("amenities" in e for e in rows[6]["errors"])
    assert rows[7]["errors"] == ["Invalid WhatsApp number"]
    async with get_sessionmaker()() as s:
        assert (await s.scalars(select(Listing))).all() == []

    r = await post(broker, data, dry_run=False)
    body = r.json()
    assert body["created"] == 3
    ids = [x["listing_id"] for x in body["rows"] if x["ok"]]
    assert len(ids) == 3 and all(ids)
    mine = (await broker.client.get("/api/v1/me/listings")).json()
    assert {x["id"] for x in mine} == set(ids)
    assert all(x["status"] == "draft" for x in mine)
    sale = next(x for x in mine if x["title"]["ar"] == "شقة عربية")
    assert sale["transaction_type"] == "sale" and sale["price_period"] == "total"
    assert next(x for x in mine if x["title"]["en"] == "Hamra flat")["price_usd"] == 1500
    async with get_sessionmaker()() as s:
        assert "listing.import" in (await s.scalars(select(AuditLog.action))).all()
    assert any("CSV import" in m and "3 draft" in m for m in notifications.messages)


async def test_import_rejections(make_actor: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Agency")
    seeker = await make_actor("seeker", "s@example.com")
    anon = await make_actor()
    good = make_csv([row()])
    assert (await post(seeker, good, dry_run=True)).status_code == 403
    assert (await post(anon, good, dry_run=True)).status_code == 401

    r = await post(broker, make_csv([row()], columns=["title_en", "price_usd"]), dry_run=True)
    assert r.status_code == 422 and "Missing columns" in r.json()["error"]["message"]
    assert (await post(broker, make_csv([]), dry_run=True)).status_code == 422
    assert (await post(broker, make_csv([row()] * 201), dry_run=True)).status_code == 422
    assert (await post(broker, b"x" * (1024 * 1024 + 10), dry_run=True)).status_code == 413
    assert (await post(broker, b"\xff\xfe\x00bad", dry_run=True)).status_code in (422,)

    # Nothing valid -> nothing created even when not a dry run
    r = await post(broker, make_csv([row(location="atlantis")]), dry_run=False)
    assert r.status_code == 200 and r.json()["created"] == 0


async def test_import_accepts_cp1256_excel_exports(make_actor: Any) -> None:
    owner = await make_actor("owner", "o@example.com")
    data = make_csv([row(location="الأشرفية", title_en="", title_ar="شقة")], encoding="cp1256")
    r = await post(owner, data, dry_run=True)
    assert r.status_code == 200 and r.json()["valid"] == 1
