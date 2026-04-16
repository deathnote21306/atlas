from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas_api.models import Country, FxRate, MacroIndicatorVintage, RatingHistory


def list_countries(session: Session) -> list[Country]:
    return list(session.execute(select(Country).order_by(Country.iso3)).scalars())


def get_country(session: Session, iso3: str) -> Country | None:
    return session.get(Country, iso3)


def get_latest(session: Session, iso3: str, indicator: str) -> MacroIndicatorVintage | None:
    return session.execute(
        select(MacroIndicatorVintage)
        .where(
            MacroIndicatorVintage.iso3 == iso3.upper(),
            MacroIndicatorVintage.indicator == indicator,
        )
        .order_by(
            MacroIndicatorVintage.period.desc(),
            MacroIndicatorVintage.ingested_at.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()


def get_as_of(
    session: Session, iso3: str, indicator: str, vintage_id: UUID
) -> MacroIndicatorVintage | None:
    return session.execute(
        select(MacroIndicatorVintage)
        .where(
            MacroIndicatorVintage.iso3 == iso3.upper(),
            MacroIndicatorVintage.indicator == indicator,
            MacroIndicatorVintage.vintage_id == vintage_id,
        )
        .order_by(MacroIndicatorVintage.period.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_latest_fx(session: Session, iso3: str) -> FxRate | None:
    return session.execute(
        select(FxRate)
        .where(FxRate.iso3 == iso3.upper())
        .order_by(FxRate.observation_date.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_fx_on(session: Session, iso3: str, d: date) -> FxRate | None:
    return session.execute(
        select(FxRate)
        .where(FxRate.iso3 == iso3.upper(), FxRate.observation_date <= d)
        .order_by(FxRate.observation_date.desc())
        .limit(1)
    ).scalar_one_or_none()


def compute_fx_deltas(session: Session, iso3: str) -> dict[str, float | None]:
    latest = get_latest_fx(session, iso3)
    if latest is None:
        return {
            "delta_1d_pct": None,
            "delta_7d_pct": None,
            "delta_30d_pct": None,
            "delta_ytd_pct": None,
        }
    base = latest.observation_date

    def pct(past: FxRate | None) -> float | None:
        if past is None or past.usd_per_ccy == 0:
            return None
        return float((latest.usd_per_ccy - past.usd_per_ccy) / past.usd_per_ccy) * 100.0

    return {
        "delta_1d_pct": pct(get_fx_on(session, iso3, base - timedelta(days=1))),
        "delta_7d_pct": pct(get_fx_on(session, iso3, base - timedelta(days=7))),
        "delta_30d_pct": pct(get_fx_on(session, iso3, base - timedelta(days=30))),
        "delta_ytd_pct": pct(get_fx_on(session, iso3, date(base.year, 1, 1))),
    }


def get_rating_history(
    session: Session, iso3: str, agency: str | None = None
) -> list[RatingHistory]:
    stmt = select(RatingHistory).where(RatingHistory.iso3 == iso3.upper())
    if agency is not None:
        stmt = stmt.where(RatingHistory.agency == agency)
    stmt = stmt.order_by(RatingHistory.action_date.desc())
    return list(session.execute(stmt).scalars())
