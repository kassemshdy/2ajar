"""Public agency page."""

from datetime import datetime

from app.schemas.common import APIModel
from app.schemas.listing import ListingPublic


class AgencyPage(APIModel):
    name: str
    slug: str
    verified: bool
    is_demo: bool
    members: int
    on_2ajar_since: datetime
    listings: list[ListingPublic]
