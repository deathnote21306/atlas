from datetime import date, datetime

from pydantic import BaseModel


class FxObservation(BaseModel):
    iso3: str
    ccy: str
    usd_per_ccy: float
    observation_date: date
    source: str
    ingested_at: datetime


class FxDeltas(BaseModel):
    latest: FxObservation
    delta_1d_pct: float | None
    delta_7d_pct: float | None
    delta_30d_pct: float | None
    delta_ytd_pct: float | None
