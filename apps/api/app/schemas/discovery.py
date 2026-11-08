"""Home-page rows, nearby search and favorites."""

from typing import Literal

from app.schemas.common import APIModel
from app.schemas.listing import AreaProfileOut, ListingPublic


class ViewedListing(APIModel):
    listing: ListingPublic
    visitors_30d: int


class NearbyListing(APIModel):
    listing: ListingPublic
    distance_km: float


class ValueListing(APIModel):
    listing: ListingPublic
    below_area_median_pct: int  # how far under the area's median price per m², in percent


class RankedArea(APIModel):
    area: AreaProfileOut
    listing_count: int


class AreaRow(APIModel):
    """A row of homes in one place ("Popular homes in Batroun", "Places to stay in Faraya")."""

    slug: str
    name_en: str
    name_ar: str
    parent_en: str | None  # district / governorate, shown as the row's subtitle
    parent_ar: str | None
    kind: Literal["homes", "stays"]  # "stays" when most homes there are rented by the night or hour
    listings: list[ListingPublic]


class DiscoverOut(APIModel):
    """Each row is empty when there is nothing honest to show (e.g. no views yet), and the UI hides it."""

    recent: list[ListingPublic]
    nights: list[ListingPublic]  # chalets and holiday homes, priced per night or week
    hours: list[ListingPublic]  # day use, priced per hour or day
    most_viewed: list[ViewedListing]
    great_value: list[ValueListing]
    top_areas: list[RankedArea]
    by_area: list[AreaRow] = []  # busiest places first


class FavoriteIds(APIModel):
    listing_ids: list[str]
