from datetime import UTC, datetime
from time import monotonic

from fastapi import APIRouter
from pydantic import BaseModel

from atlas_api.deps import CurrentUser, DbSession
from atlas_api.models import FxRate
from atlas_api.services.country.indicators import ISO3_TO_CCY
from sqlalchemy import select

router = APIRouter(prefix="/api/fx", tags=["fx"])

_cache: dict[str, tuple[float, object]] = {}
CACHE_TTL = 60


class FxQuote(BaseModel):
    pair: str
    value: float
    change_pct: float


class FxTickerResponse(BaseModel):
    as_of: str
    indicative: bool
    quotes: list[FxQuote]


def _build_ticker(session: DbSession) -> FxTickerResponse:
    quotes: list[FxQuote] = []
    latest_dt: datetime | None = None

    for iso3, ccy in sorted(ISO3_TO_CCY.items(), key=lambda x: x[1]):
        if ccy == "XOF" and iso3 != "CIV":
            continue

        latest = session.execute(
            select(FxRate)
            .where(FxRate.iso3 == iso3)
            .order_by(FxRate.observation_date.desc())
            .limit(1)
        ).scalar_one_or_none()

        if latest is None:
            continue

        ccy_per_usd = 1.0 / float(latest.usd_per_ccy) if latest.usd_per_ccy != 0 else 0

        prev = session.execute(
            select(FxRate)
            .where(FxRate.iso3 == iso3, FxRate.observation_date < latest.observation_date)
            .order_by(FxRate.observation_date.desc())
            .limit(1)
        ).scalar_one_or_none()

        change_pct = 0.0
        if prev and prev.usd_per_ccy != 0:
            prev_ccy_per_usd = 1.0 / float(prev.usd_per_ccy)
            if prev_ccy_per_usd != 0:
                change_pct = round(
                    ((ccy_per_usd - prev_ccy_per_usd) / prev_ccy_per_usd) * 100, 2
                )

        quotes.append(FxQuote(
            pair=f"USD/{ccy}",
            value=round(ccy_per_usd, 2),
            change_pct=change_pct,
        ))

        if latest_dt is None or latest.ingested_at > latest_dt:
            latest_dt = latest.ingested_at

    return FxTickerResponse(
        as_of=(latest_dt or datetime.now(UTC)).isoformat(),
        indicative=True,
        quotes=quotes,
    )


@router.get("/ticker", response_model=FxTickerResponse)
def fx_ticker(session: DbSession, _: CurrentUser) -> FxTickerResponse:
    now = monotonic()
    cached = _cache.get("ticker")
    if cached and (now - cached[0]) < CACHE_TTL:
        return cached[1]  # type: ignore[return-value]

    result = _build_ticker(session)
    _cache["ticker"] = (now, result)
    return result
