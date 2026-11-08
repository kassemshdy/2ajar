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
from app.models import (
    AreaProfile,
    Listing,
    ListingMedia,
    Location,
    Organization,
    OrganizationMember,
    Property,
    User,
)
from app.models.enums import (
    Amenity,
    ElectricitySupply,
    FloodRisk,
    Furnished,
    GarbageCollection,
    ListingStatus,
    LocationLevel,
    OrgRole,
    PricePeriod,
    PropertyType,
    Sewage,
    SummerComfort,
    TransactionType,
    UserRole,
    WaterSource,
    WinterComfort,
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
                ("faraya", "Faraya", "فاريا", 34.0022, 35.8285, []),
                ("faqra", "Faqra", "فقرا", 34.0001, 35.8160, []),
                ("kfardebian", "Kfardebian", "كفرذبيان", 33.9897, 35.7633, []),
            ]),
            ("jbeil-district", "Jbeil District", "قضاء جبيل", None, None, [
                ("byblos", "Byblos", "جبيل", 34.1230, 35.6519, []),
                ("laqlouq", "Laqlouq", "اللقلوق", 34.1350, 35.8580, []),
            ]),
            ("chouf", "Chouf", "الشوف", None, None, [
                ("jiyeh", "Jiyeh", "الجية", 33.6500, 35.4200, []),
            ]),
            ("aley-district", "Aley District", "قضاء عاليه", None, None, [
                ("aley", "Aley", "عاليه", 33.8080, 35.6000, []),
                ("bchamoun", "Bchamoun", "بشامون", 33.7850, 35.5200, []),
            ]),
        ],
    ),
    ("north", "North Lebanon", "الشمال", None, None, [
        ("batroun-district", "Batroun District", "قضاء البترون", None, None, [
            ("batroun", "Batroun", "البترون", 34.2553, 35.6581, []),
        ]),
    ]),
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
        lo, hi = AREA_PRICE[loc.slug]
        factor = (0.6 + 0.25 * bedrooms) * (1.15 if furnished == Furnished.furnished else 1.0)
        monthly = int(round(rng.uniform(lo, hi) * factor / 50) * 50)
        price = max(monthly, 300)

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
            transaction_type=TransactionType.rent,
            price_usd_cents=price * 100,
            price_period=PricePeriod.monthly,
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


# Chalets and day-use places: (area slug, type, EN name, AR name, period, (min, max) USD, guests range)
SHORT_STAYS: list[tuple[str, PropertyType, str, str, PricePeriod, tuple[int, int], tuple[int, int]]] = [
    ("faraya", PropertyType.chalet, "Ski chalet", "شاليه تزلج", PricePeriod.nightly, (120, 280), (4, 8)),
    ("faqra", PropertyType.chalet, "Mountain chalet with fireplace", "شاليه جبلي مع موقدة", PricePeriod.nightly, (150, 350), (4, 10)),
    ("kfardebian", PropertyType.chalet, "Cosy A-frame chalet", "شاليه دافئ", PricePeriod.nightly, (90, 180), (2, 6)),
    ("laqlouq", PropertyType.chalet, "Forest cabin", "كوخ في الغابة", PricePeriod.weekly, (500, 900), (2, 6)),
    ("batroun", PropertyType.chalet, "Beach chalet", "شاليه على البحر", PricePeriod.nightly, (110, 260), (2, 6)),
    ("byblos", PropertyType.apartment, "Old-souk holiday flat", "شقة عطلات قرب السوق القديم", PricePeriod.nightly, (70, 140), (2, 4)),
    ("jiyeh", PropertyType.chalet, "Seafront chalet", "شاليه على الواجهة البحرية", PricePeriod.nightly, (100, 220), (4, 8)),
    ("jiyeh", PropertyType.chalet, "Day-use chalet with private pool", "شاليه نهاري مع مسبح خاص", PricePeriod.hourly, (20, 45), (6, 15)),
    ("batroun", PropertyType.house, "Garden & pool for the day", "حديقة ومسبح ليوم", PricePeriod.daily, (120, 250), (8, 20)),
    ("jounieh", PropertyType.office, "Meeting room by the hour", "قاعة اجتماعات بالساعة", PricePeriod.hourly, (10, 25), (4, 12)),
]  # fmt: skip
PERIOD_LABEL = {
    PricePeriod.hourly: ("per hour", "بالساعة"),
    PricePeriod.daily: ("per day", "باليوم"),
    PricePeriod.nightly: ("per night", "بالليلة"),
    PricePeriod.weekly: ("per week", "بالأسبوع"),
}


async def seed_demo_short_stays(session: AsyncSession) -> int:
    """Demo chalets and day-use places (per hour / day / night / week). Idempotent; needs the demo accounts."""
    short = (PricePeriod.hourly, PricePeriod.daily, PricePeriod.nightly, PricePeriod.weekly)
    exists = select(Listing.id).where(Listing.is_demo.is_(True), Listing.price_period.in_(short)).limit(1)
    if await session.scalar(exists):
        return 0
    hosts = list(
        (await session.scalars(select(User).where(User.is_demo.is_(True)).order_by(User.email))).all()
    )
    if not hosts:
        return 0
    slugs = {s[0] for s in SHORT_STAYS}
    areas = {
        x.slug: x for x in (await session.scalars(select(Location).where(Location.slug.in_(slugs)))).all()
    }
    storage = get_storage()
    now = utcnow()
    rng = random.Random(1961)
    created = 0
    for i, (slug, ptype, name_en, name_ar, period, (lo, hi), (g_lo, g_hi)) in enumerate(SHORT_STAYS):
        loc = areas.get(slug)
        if loc is None:
            continue
        host = hosts[i % len(hosts)]
        member = await session.scalar(select(OrganizationMember).where(OrganizationMember.user_id == host.id))
        guests = rng.randint(g_lo, g_hi)
        bedrooms = None if ptype == PropertyType.office else max(1, guests // 2 - rng.randint(0, 1))
        amenities = [Amenity.parking.value, Amenity.generator_24_7.value]
        amenities += rng.sample(
            [Amenity.pool.value, Amenity.mountain_view.value, Amenity.sea_view.value, Amenity.garden.value,
             Amenity.terrace.value, Amenity.pets_allowed.value], 2
        )  # fmt: skip
        price = int(round(rng.randint(lo, hi) / 5) * 5)
        per_en, per_ar = PERIOD_LABEL[period]
        prop = Property(
            owner_user_id=host.id, organization_id=member.organization_id if member else None,
            location_id=loc.id, property_type=ptype, bedrooms=bedrooms, bathrooms=1 if bedrooms else None,
            area_sqm=rng.randint(60, 220), max_guests=guests, furnished=Furnished.furnished,
            amenities=amenities, lat=loc.lat, lng=loc.lng, is_demo=True,
        )  # fmt: skip
        session.add(prop)
        await session.flush()
        published_at = now - timedelta(days=rng.randint(0, 10), hours=rng.randint(0, 23))
        listing = Listing(
            property_id=prop.id, created_by_user_id=host.id, organization_id=prop.organization_id,
            transaction_type=TransactionType.rent, price_usd_cents=price * 100, price_period=period,
            status=ListingStatus.published, title_en=f"{name_en} in {loc.name_en}",
            title_ar=f"{name_ar} في {loc.name_ar}",
            description_en=f"[DEMO LISTING - not a real property] Up to {guests} guests, ${price} {per_en}.",
            description_ar=f"[إعلان تجريبي - ليس عقاراً حقيقياً] حتى {guests} ضيوف، {price}$ {per_ar}.",
            contact_whatsapp_e164=host.phone_e164, published_at=published_at, last_confirmed_at=published_at,
            expires_at=published_at + timedelta(days=get_settings().listing_ttl_days), is_demo=True,
        )  # fmt: skip
        session.add(listing)
        await session.flush()
        data = _placeholder_image(rng, loc.name_en)
        key = f"listings/{listing.id}/demo-0.webp"
        await storage.put(key, data, "image/webp")
        session.add(ListingMedia(listing_id=listing.id, storage_key=key, content_type="image/webp",
                                 width=1200, height=800, byte_size=len(data), position=0))  # fmt: skip
        created += 1
    await session.commit()
    return created


DEMO_AREA_NOTE = "Synthetic demo values, not real statistics"
DEMO_HIGHLIGHTS = (
    ("Lots of natural light", "إضاءة طبيعية كثيرة"),
    ("Walking distance to shops", "قريب من المحلات سيراً"),
    ("Recently renovated kitchen", "مطبخ مجدد حديثاً"),
    ("Open view from the balcony", "إطلالة مفتوحة من الشرفة"),
)
DEMO_THINGS_TO_KNOW = (
    ("Generator subscription paid separately", "اشتراك المولد يُدفع منفصلاً"),
    ("Street can be busy at rush hour", "الشارع مزدحم وقت الذروة"),
    ("Water tank on the roof", "خزان مياه على السطح"),
)


async def seed_demo_living(session: AsyncSession) -> int:
    """Fill living factors on demo properties that have none yet (idempotent; safe on every deploy)."""
    props = list(
        (
            await session.scalars(
                select(Property).where(Property.is_demo.is_(True), Property.electricity_supply.is_(None))
            )
        ).all()
    )
    for prop in props:
        rng = random.Random(str(prop.id))  # stable per property
        supply = rng.choice(list(ElectricitySupply))
        amps = (
            None
            if supply in (ElectricitySupply.edl_only, ElectricitySupply.solar)
            else rng.choice((5, 10, 15))
        )
        bill = {
            ElectricitySupply.edl_only: rng.randint(10, 30),
            ElectricitySupply.edl_plus_generator: rng.randint(50, 140),
            ElectricitySupply.generator_24_7: rng.randint(80, 200),
            ElectricitySupply.solar: rng.randint(10, 40),
            ElectricitySupply.solar_battery: rng.randint(15, 50),
        }[supply]
        water = rng.choice(list(WaterSource))
        lang = 0 if rng.random() < 0.5 else 1
        prop.electricity_supply = supply
        prop.generator_amps = amps
        prop.electricity_usd_month = bill
        prop.water_source = water
        prop.water_usd_month = (
            rng.randint(8, 18) if water in (WaterSource.municipal, WaterSource.well) else rng.randint(20, 60)
        )
        prop.sewage = Sewage.public_network if rng.random() < 0.8 else Sewage.septic_tank
        prop.parking_spots = rng.choice((0, 1, 1, 2))
        prop.solar_ready = rng.random() < 0.5
        prop.elevator_backup = (
            rng.random() < 0.7 if Amenity.elevator.value in (prop.amenities or []) else None
        )
        prop.winter_comfort = rng.choice(list(WinterComfort))
        prop.summer_comfort = rng.choice(list(SummerComfort))
        prop.highlights = [h[lang] for h in rng.sample(DEMO_HIGHLIGHTS, 2)]
        prop.things_to_know = [t[lang] for t in rng.sample(DEMO_THINGS_TO_KNOW, 1)]
    await session.commit()
    return len(props)


async def seed_demo_areas(session: AsyncSession) -> int:
    """Create clearly-marked demo area profiles for demo areas that have no profile (never overwrites)."""
    existing = set((await session.scalars(select(AreaProfile.location_id))).all())
    slugs = {*AREA_PRICE, *(s[0] for s in SHORT_STAYS)}
    areas = (await session.scalars(select(Location).where(Location.slug.in_(slugs)))).all()
    created = 0
    for loc in areas:
        if loc.id in existing:
            continue
        rng = random.Random(loc.slug)
        safety = rng.randint(2, 5)
        session.add(
            AreaProfile(
                location_id=loc.id,
                safety_score=safety,
                theft_reports_12m=rng.randint(0, 6) if safety >= 4 else rng.randint(5, 30),
                quiet_score=rng.randint(2, 5),
                garbage_collection=rng.choice(list(GarbageCollection)),
                flood_risk=rng.choice((FloodRisk.low, FloodRisk.low, FloodRisk.medium, FloodRisk.high)),
                noise_notes_en="[DEMO] Example note: some barking dogs at night.",
                noise_notes_ar="[تجريبي] ملاحظة مثال: نباح كلاب أحياناً ليلاً.",
                summary_en=f"[DEMO] Illustrative profile for {loc.name_en}. {DEMO_AREA_NOTE}.",
                summary_ar=f"[تجريبي] ملف توضيحي لمنطقة {loc.name_ar}. قيم تجريبية وليست إحصاءات حقيقية.",
                source_note=DEMO_AREA_NOTE,
                is_demo=True,
            )
        )
        created += 1
    await session.commit()
    return created


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
    await session.execute(delete(AreaProfile).where(AreaProfile.is_demo.is_(True)))
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
            print(f"demo short stays created: {await seed_demo_short_stays(session)}")
            print(f"demo living factors filled: {await seed_demo_living(session)}")
            print(f"demo area profiles created: {await seed_demo_areas(session)}")
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
