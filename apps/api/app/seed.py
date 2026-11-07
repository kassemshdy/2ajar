"""Seed Lebanese locations and clearly-marked DEMO listings.

Usage:  python -m app.seed               (locations only: safe everywhere)
        python -m app.seed --demo        (+ demo listings; refused when ENV=production)
        python -m app.seed --purge-demo  (delete all demo data)

Locations are real public geography. Every person, agency, listing and phone number created here is
synthetic and flagged `is_demo = true`.
"""

import argparse
import asyncio
import io
import os
import random
import secrets
import sys
from datetime import timedelta
from decimal import Decimal

from PIL import Image, ImageDraw
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password, utcnow
from app.db.session import get_sessionmaker
from app.models import Listing, ListingMedia, Location, Organization, OrganizationMember, Property, User
from app.models.enums import (
    Amenity,
    Furnished,
    ListingStatus,
    LocationLevel,
    OrgRole,
    PricePeriod,
    PropertyType,
    TransactionType,
    UserRole,
)
from app.repositories.locations import LocationDirectory
from app.services.superuser import ensure_superuser
from app.storage import get_storage

# (slug, name_en, name_ar, lat, lng, children)
LocationSpec = tuple[str, str, str, float | None, float | None, list["LocationSpec"]]

AREAS_BEIRUT: list[LocationSpec] = [
    ("achrafieh", "Achrafieh", "الأشرفية", 33.8880, 35.5200, []),
    ("hamra", "Hamra", "الحمرا", 33.8960, 35.4820, []),
    ("mar-mikhael", "Mar Mikhael", "مار مخايل", 33.8970, 35.5270, []),
    ("gemmayzeh", "Gemmayzeh", "الجميزة", 33.8950, 35.5170, []),
    ("verdun", "Verdun", "فردان", 33.8840, 35.4840, []),
    ("ras-beirut", "Ras Beirut", "رأس بيروت", 33.9000, 35.4750, []),
    ("badaro", "Badaro", "بدارو", 33.8730, 35.5130, []),
    ("downtown-beirut", "Downtown", "وسط بيروت", 33.8960, 35.5050, []),
    ("ain-el-mreisseh", "Ain El Mreisseh", "عين المريسة", 33.9010, 35.4900, []),
    ("mazraa", "Mazraa", "المزرعة", 33.8770, 35.4950, []),
]

LOCATIONS: list[LocationSpec] = [
    ("beirut", "Beirut", "بيروت", 33.8938, 35.5018, AREAS_BEIRUT),
    (
        "mount-lebanon",
        "Mount Lebanon",
        "جبل لبنان",
        None,
        None,
        [
            ("metn", "Metn", "المتن", None, None, [
                ("jdeideh", "Jdeideh", "الجديدة", 33.8930, 35.5650, []),
                ("dbayeh", "Dbayeh", "ضبية", 33.9370, 35.5900, []),
                ("antelias", "Antelias", "أنطلياس", 33.9150, 35.5850, []),
                ("sin-el-fil", "Sin El Fil", "سن الفيل", 33.8750, 35.5450, []),
                ("jal-el-dib", "Jal El Dib", "جل الديب", 33.9100, 35.5800, []),
                ("bikfaya", "Bikfaya", "بكفيا", 33.9220, 35.6800, []),
            ]),
            ("baabda-district", "Baabda District", "قضاء بعبدا", None, None, [
                ("hazmieh", "Hazmieh", "الحازمية", 33.8550, 35.5400, []),
                ("hadath", "Hadath", "الحدث", 33.8350, 35.5250, []),
                ("baabda", "Baabda", "بعبدا", 33.8340, 35.5450, []),
                ("furn-el-chebbak", "Furn El Chebbak", "فرن الشباك", 33.8670, 35.5300, []),
            ]),
            ("keserwan", "Keserwan", "كسروان", None, None, [
                ("jounieh", "Jounieh", "جونية", 33.9810, 35.6180, []),
                ("zouk-mosbeh", "Zouk Mosbeh", "ذوق مصبح", 33.9550, 35.6050, []),
                ("kaslik", "Kaslik", "الكسليك", 33.9730, 35.6160, []),
                ("adma", "Adma", "أدما", 33.9980, 35.6400, []),
            ]),
            ("aley-district", "Aley District", "قضاء عاليه", None, None, [
                ("aley", "Aley", "عاليه", 33.8080, 35.6000, []),
                ("bchamoun", "Bchamoun", "بشامون", 33.7850, 35.5200, []),
            ]),
        ],
    ),
]  # fmt: skip

LEVELS = [LocationLevel.governorate, LocationLevel.district, LocationLevel.area]


async def seed_locations(session: AsyncSession) -> int:
    created = 0

    async def upsert(spec: LocationSpec, parent: Location | None, depth: int) -> None:
        nonlocal created
        slug, en, ar, lat, lng, children = spec
        path = f"{parent.path}/{slug}" if parent else slug
        # Beirut has no district level in our tree: its children are areas.
        level = LocationLevel.area if (parent is not None and not children) else LEVELS[min(depth, 2)]
        loc = await session.scalar(select(Location).where(Location.slug == slug))
        if loc is None:
            loc = Location(slug=slug, path=path, name_en=en, name_ar=ar, level=level)
            session.add(loc)
            created += 1
        loc.parent_id = parent.id if parent else None
        loc.name_en, loc.name_ar, loc.path, loc.level = en, ar, path, level
        loc.lat = Decimal(str(lat)) if lat is not None else None
        loc.lng = Decimal(str(lng)) if lng is not None else None
        await session.flush()
        for child in children:
            await upsert(child, loc, depth + 1)

    for spec in LOCATIONS:
        await upsert(spec, None, 0)
    await session.commit()
    LocationDirectory.invalidate()  # cached reference data must reflect the new tree
    return created


# ---------------- demo data ----------------

DEMO_DOMAIN = "demo.2ajar.invalid"

AREA_PRICE = {  # monthly rent range in USD for a 2-bedroom, rough synthetic baseline
    "achrafieh": (900, 1800), "hamra": (700, 1400), "mar-mikhael": (900, 1700), "gemmayzeh": (850, 1600),
    "verdun": (1200, 2500), "ras-beirut": (1000, 2200), "badaro": (700, 1300), "downtown-beirut": (1800, 4000),
    "ain-el-mreisseh": (1100, 2400), "mazraa": (500, 1000), "jdeideh": (450, 850), "dbayeh": (800, 1600),
    "antelias": (650, 1200), "sin-el-fil": (600, 1100), "jal-el-dib": (600, 1100), "bikfaya": (500, 1000),
    "hazmieh": (700, 1300), "hadath": (450, 850), "baabda": (600, 1200), "furn-el-chebbak": (500, 950),
    "jounieh": (600, 1200), "zouk-mosbeh": (550, 1000), "kaslik": (700, 1300), "adma": (900, 2000),
    "aley": (400, 800), "bchamoun": (400, 750),
}  # fmt: skip

TYPE_LABEL = {
    PropertyType.apartment: ("apartment", "شقة"),
    PropertyType.studio: ("studio", "استوديو"),
    PropertyType.duplex: ("duplex", "دوبلكس"),
    PropertyType.villa: ("villa", "فيلا"),
}
FURNISHED_LABEL = {
    Furnished.furnished: ("Furnished", "مفروشة"),
    Furnished.semi: ("Semi-furnished", "نصف مفروشة"),
    Furnished.unfurnished: ("Unfurnished", "غير مفروشة"),
}
AMENITY_LABEL = {
    Amenity.generator_24_7: ("24/7 generator", "مولد ٢٤/٧"),
    Amenity.solar_power: ("solar panels", "طاقة شمسية"),
    Amenity.elevator: ("elevator", "مصعد"),
    Amenity.parking: ("parking", "موقف سيارة"),
    Amenity.balcony: ("balcony", "شرفة"),
    Amenity.sea_view: ("sea view", "إطلالة بحرية"),
    Amenity.mountain_view: ("mountain view", "إطلالة جبلية"),
    Amenity.air_conditioning: ("A/C", "تكييف"),
    Amenity.water_tank: ("water tank", "خزان مياه"),
    Amenity.security: ("security", "حراسة"),
}

PALETTE = [(31, 78, 121), (46, 125, 50), (142, 68, 173), (192, 57, 43), (211, 84, 0), (22, 160, 133)]


def _placeholder_image(rng: random.Random, label: str) -> bytes:
    w, h = 1200, 800
    c1 = rng.choice(PALETTE)
    c2 = tuple(min(255, v + 70) for v in c1)
    img = Image.new("RGB", (w, h), c1)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        draw.line([(0, y), (w, y)], fill=tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3)))
    # simple building silhouette
    for i in range(5):
        bx = 120 + i * 200
        bh = rng.randint(250, 500)
        draw.rectangle([bx, h - bh, bx + 150, h], fill=(255, 255, 255, 40), outline=(255, 255, 255))
        for wy in range(h - bh + 30, h - 40, 60):
            for wx in (bx + 25, bx + 85):
                draw.rectangle([wx, wy, wx + 35, wy + 30], fill=(255, 236, 179))
    draw.text((40, 40), f"DEMO - {label}", fill=(255, 255, 255))
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=70)
    return out.getvalue()


async def _demo_user(
    session: AsyncSession, email: str, name: str, role: UserRole, phone: str, password_hash: str
) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, full_name=name, role=role, phone_e164=phone, password_hash=password_hash,
                    is_demo=True, locale="en")  # fmt: skip
        session.add(user)
        await session.flush()
    return user


async def seed_demo(session: AsyncSession, count: int = 30) -> int:
    if await session.scalar(select(Listing.id).where(Listing.is_demo.is_(True)).limit(1)):
        return 0  # idempotent: demo listings already present

    password = os.environ.get("SEED_DEMO_PASSWORD") or secrets.token_urlsafe(24)
    pw_hash = hash_password(password)
    rng = random.Random(961)

    org_specs = [("Cedar Homes (Demo)", "cedar-homes-demo"), ("Sea Breeze Realty (Demo)", "sea-breeze-demo")]
    orgs = []
    for name, slug in org_specs:
        org = await session.scalar(select(Organization).where(Organization.slug == slug))
        if org is None:
            org = Organization(name=name, slug=slug, is_demo=True, is_verified=True)
            session.add(org)
            await session.flush()
        orgs.append(org)

    brokers = [
        (await _demo_user(session, f"rami.broker@{DEMO_DOMAIN}", "Rami Demo", UserRole.broker,
                          "+96170000101", pw_hash), orgs[0], OrgRole.agency_admin),
        (await _demo_user(session, f"nour.broker@{DEMO_DOMAIN}", "Nour Demo", UserRole.broker,
                          "+96170000102", pw_hash), orgs[0], OrgRole.agent),
        (await _demo_user(session, f"karim.broker@{DEMO_DOMAIN}", "Karim Demo", UserRole.broker,
                          "+96170000103", pw_hash), orgs[1], OrgRole.agency_admin),
    ]  # fmt: skip
    for user, org, role in brokers:
        exists = await session.scalar(
            select(OrganizationMember.id).where(
                OrganizationMember.user_id == user.id, OrganizationMember.organization_id == org.id
            )
        )
        if not exists:
            session.add(OrganizationMember(user_id=user.id, organization_id=org.id, role=role))
    owners = [
        await _demo_user(session, f"maya.owner@{DEMO_DOMAIN}", "Maya Demo", UserRole.owner, "+96170000201", pw_hash),
        await _demo_user(session, f"georges.owner@{DEMO_DOMAIN}", "Georges Demo", UserRole.owner,
                         "+96170000202", pw_hash),
    ]  # fmt: skip
    await session.flush()

    areas = list((await session.scalars(select(Location).where(Location.slug.in_(AREA_PRICE)))).all())
    storage = get_storage()
    now = utcnow()
    amenity_pool = list(AMENITY_LABEL)
    ptypes = [PropertyType.apartment] * 6 + [PropertyType.studio, PropertyType.duplex, PropertyType.villa]

    for i in range(count):
        loc = areas[i % len(areas)] if i < len(areas) else rng.choice(areas)
        ptype = rng.choice(ptypes)
        bedrooms = {PropertyType.studio: 0, PropertyType.villa: rng.randint(3, 5)}.get(
            ptype, rng.randint(1, 4)
        )
        bathrooms = max(1, bedrooms - rng.randint(0, 1)) if bedrooms else 1
        area_sqm = {0: rng.randint(35, 60)}.get(bedrooms, 45 + bedrooms * rng.randint(35, 55))
        furnished = rng.choice(list(Furnished))
        amenities = sorted(rng.sample(amenity_pool, rng.randint(2, 5)), key=amenity_pool.index)
        is_sale = i % 7 == 6
        lo, hi = AREA_PRICE[loc.slug]
        factor = (0.6 + 0.25 * bedrooms) * (1.15 if furnished == Furnished.furnished else 1.0)
        monthly = int(round(rng.uniform(lo, hi) * factor / 50) * 50)
        price = int(round(monthly * rng.uniform(170, 230) / 1000) * 1000) if is_sale else max(monthly, 300)

        if i % 3 == 2:
            creator, org_id = owners[i % 2], None
        else:
            b_user, b_org, _ = brokers[i % 3]
            creator, org_id = b_user, b_org.id

        t_en, t_ar = TYPE_LABEL[ptype]
        f_en, f_ar = FURNISHED_LABEL[furnished]
        rooms_en = "Studio" if bedrooms == 0 else f"{bedrooms}-bedroom"
        rooms_ar = {0: "", 1: " من غرفة نوم واحدة", 2: " من غرفتي نوم"}.get(
            bedrooms, f" من {bedrooms} غرف نوم"
        )
        title_en = (
            f"{f_en} {rooms_en} {t_en} in {loc.name_en}" if bedrooms else f"{f_en} studio in {loc.name_en}"
        )
        title_ar = f"{t_ar}{rooms_ar} {f_ar} في {loc.name_ar}"
        am_en = ", ".join(AMENITY_LABEL[a][0] for a in amenities)
        am_ar = "، ".join(AMENITY_LABEL[a][1] for a in amenities)
        floor = rng.randint(0, 12)
        desc_en = (
            f"[DEMO LISTING - not a real property] {area_sqm} sqm on floor {floor}. "
            f"{bathrooms} bathroom(s). Features: {am_en}."
        )
        desc_ar = (
            f"[إعلان تجريبي - ليس عقاراً حقيقياً] المساحة {area_sqm} م² في الطابق {floor}. "
            f"عدد الحمامات: {bathrooms}. المميزات: {am_ar}."
        )

        prop = Property(
            owner_user_id=creator.id, organization_id=org_id, location_id=loc.id, property_type=ptype,
            bedrooms=bedrooms, bathrooms=bathrooms, area_sqm=area_sqm, floor=floor, furnished=furnished,
            amenities=[a.value for a in amenities], lat=loc.lat, lng=loc.lng, is_demo=True,
        )  # fmt: skip
        session.add(prop)
        await session.flush()
        published_at = now - timedelta(days=rng.randint(0, 20), hours=rng.randint(0, 23))
        listing = Listing(
            property_id=prop.id,
            created_by_user_id=creator.id,
            organization_id=org_id,
            transaction_type=TransactionType.sale if is_sale else TransactionType.rent,
            price_usd_cents=price * 100,
            price_period=PricePeriod.total if is_sale else PricePeriod.monthly,
            status=ListingStatus.published,
            title_en=title_en,
            title_ar=title_ar,
            description_en=desc_en,
            description_ar=desc_ar,
            contact_whatsapp_e164=creator.phone_e164,
            published_at=published_at,
            last_confirmed_at=published_at,
            expires_at=published_at + timedelta(days=get_settings().listing_ttl_days),
            is_demo=True,
        )
        session.add(listing)
        await session.flush()
        data = _placeholder_image(rng, loc.name_en)
        key = f"listings/{listing.id}/demo-0.webp"
        await storage.put(key, data, "image/webp")
        session.add(ListingMedia(listing_id=listing.id, storage_key=key, content_type="image/webp",
                                 width=1200, height=800, byte_size=len(data), position=0))  # fmt: skip

    await session.commit()
    if os.environ.get("SEED_DEMO_PASSWORD"):
        print(f"Demo accounts use SEED_DEMO_PASSWORD (e.g. rami.broker@{DEMO_DOMAIN})")
    return count


async def purge_demo(session: AsyncSession) -> int:
    """Delete all demo listings, properties, accounts and organizations (and their stored photos)."""
    storage = get_storage()
    keys = list(
        (
            await session.scalars(
                select(ListingMedia.storage_key).join(Listing).where(Listing.is_demo.is_(True))
            )
        ).all()
    )
    listing_ids = list((await session.scalars(select(Listing.id).where(Listing.is_demo.is_(True)))).all())
    await session.execute(delete(Listing).where(Listing.is_demo.is_(True)))
    await session.execute(delete(Property).where(Property.is_demo.is_(True)))
    demo_users = select(User.id).where(User.is_demo.is_(True))
    await session.execute(delete(OrganizationMember).where(OrganizationMember.user_id.in_(demo_users)))
    await session.execute(delete(User).where(User.is_demo.is_(True)))
    await session.execute(delete(Organization).where(Organization.is_demo.is_(True)))
    await session.commit()
    for key in keys:
        await storage.delete(key)
    return len(listing_ids)


async def main(demo: bool = False, purge: bool = False) -> int:
    s = get_settings()
    if demo and s.env == "production":
        print("Refusing to seed demo data: ENV=production", file=sys.stderr)
        return 2
    async with get_sessionmaker()() as session:
        if purge:
            n = await purge_demo(session)
            print(f"demo listings deleted: {n}")
            return 0
        n_loc = await seed_locations(session)
        print(f"locations created: {n_loc}")
        su = await ensure_superuser(session, s)
        if su.email:
            print(f"superuser {su.email}: {su.action}")  # never print the password
        if demo:
            n = await seed_demo(session)
            print(f"demo listings created: {n} (is_demo=true; visible only when DEMO_MODE=true)")
    return 0


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed reference data (locations) and optional demo listings."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--demo", action="store_true", help="also create clearly-marked demo listings")
    group.add_argument("--purge-demo", action="store_true", help="delete all demo data")
    args = parser.parse_args(argv)
    return asyncio.run(main(demo=args.demo, purge=args.purge_demo))


if __name__ == "__main__":
    sys.exit(cli())
