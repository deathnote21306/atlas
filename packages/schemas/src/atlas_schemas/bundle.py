from pydantic import BaseModel

from atlas_schemas.country import Country
from atlas_schemas.fx import FxDeltas
from atlas_schemas.macro import MacroIndicator
from atlas_schemas.ratings import RatingAction
from atlas_schemas.risk import RiskScore
from atlas_schemas.staleness import StalenessInfo


class MacroTile(BaseModel):
    indicator: MacroIndicator
    label: str
    value: float | None
    period: str | None
    source: str | None
    staleness: StalenessInfo


class RatingsSection(BaseModel):
    latest_per_agency: dict[str, RatingAction]
    composite_score: float | None
    history: list[RatingAction]


class CountryBundle(BaseModel):
    country: Country
    macro: list[MacroTile]
    fx: FxDeltas | None
    ratings: RatingsSection
    risk: RiskScore
    synopsis: str | None = None
    news_placeholder: bool = True
