"""Admin → Growth: Hormozi value equation and marketing playbook measured on 2ajar's data."""

from typing import Any, Literal

from pydantic import BaseModel


class FactorOut(BaseModel):
    key: Literal["dream", "likelihood", "time", "effort"]
    score: float | None  # 0..1, higher = better for the customer; None = not enough data yet
    value: str
    metric: str


class ValueEquationOut(BaseModel):
    index: float | None  # 100 * dream * likelihood / (delay * effort); None until every factor has data
    factors: list[FactorOut]


class TargetOut(BaseModel):
    day30: float
    day90: float


class FunnelOut(BaseModel):
    searches: int
    visitors: int
    views: int
    inquiries: int


class AreaGapOut(BaseModel):
    slug: str
    name_en: str
    name_ar: str
    searches: int
    zero_results: int
    live_listings: int
    has_area_facts: bool


class WishOut(BaseModel):
    key: str
    searches: int
    data_coverage: float | None  # share of live listings that can answer this wish


class CountOut(BaseModel):
    key: str
    searches: int


class QuietListingOut(BaseModel):
    id: str
    title: str
    visitors: int


class RecommendationOut(BaseModel):
    key: str
    priority: int
    lever: Literal["dream", "likelihood", "time", "effort", "leads"]
    channel: str | None
    params: dict[str, Any]


class PlaybookItemOut(BaseModel):
    key: str
    phase: int
    metric: str | None
    target: float | None
    current: float | None
    progress: float | None
    done: bool
    auto: bool


class GrowthOut(BaseModel):
    generated_at: str
    demo_mode: bool
    metrics: dict[str, float | int | None]
    targets: dict[str, TargetOut]
    renters: ValueEquationOut
    owners: ValueEquationOut
    funnel: FunnelOut
    area_gaps: list[AreaGapOut]
    wishes: list[WishOut]
    property_types: list[CountOut]
    quiet_listings: list[QuietListingOut]
    recommendations: list[RecommendationOut]
    playbook: list[PlaybookItemOut]


class GrowthTaskIn(BaseModel):
    done: bool
