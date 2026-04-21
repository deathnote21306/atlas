"""Compose the country detail bundle from stored reads + calculated metrics."""

from atlas_schemas.bundle import CountryBundle, MacroTile, RatingsSection
from atlas_schemas.country import Country as CountrySchema
from atlas_schemas.fx import FxDeltas, FxObservation
from atlas_schemas.macro import MacroIndicator
from atlas_schemas.ratings import RatingAction
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas_api.models import REERHistory, Synopsis
from atlas_api.services.country.composite_rating import composite_score
from atlas_api.services.country.economic_structure import get_economic_structure
from atlas_api.services.country.queries import (
    compute_fx_deltas,
    get_country,
    get_latest,
    get_latest_fx,
    get_rating_history,
)
from atlas_api.services.country.risk_score import compute_risk_score
from atlas_api.services.country.staleness import classify_staleness
from atlas_api.services.forecast.compute_forecasts import get_forecasts

_TILE_LABELS: dict[MacroIndicator, str] = {
    MacroIndicator.GDP_USD: "GDP (USD, current)",
    MacroIndicator.GDP_GROWTH_PCT: "GDP growth (% YoY)",
    MacroIndicator.INFLATION_PCT: "Inflation (CPI % YoY)",
    MacroIndicator.CURRENT_ACCOUNT_PCT_GDP: "Current account (% GDP)",
    MacroIndicator.FISCAL_BALANCE_PCT_GDP: "Fiscal balance (% GDP)",
    MacroIndicator.PUBLIC_DEBT_PCT_GDP: "Public debt (% GDP)",
    MacroIndicator.EXTERNAL_DEBT_PCT_GNI: "External debt (% GNI)",
    MacroIndicator.FX_RESERVES_MO_IMPORTS: "Reserves (months of imports)",
    MacroIndicator.DEBT_SERVICE_PCT_EXPORTS: "Debt service (% exports)",
    MacroIndicator.UNEMPLOYMENT_PCT: "Unemployment (%)",
    MacroIndicator.FDI_INFLOW_USD: "FDI inflow (USD)",
    MacroIndicator.GDP_PER_CAPITA_USD: "GDP per capita (USD)",
}


def _macro_tiles(session: Session, iso3: str) -> list[MacroTile]:
    tiles: list[MacroTile] = []
    for indicator, label in _TILE_LABELS.items():
        row = get_latest(session, iso3, indicator.value)
        tiles.append(
            MacroTile(
                indicator=indicator,
                label=label,
                value=float(row.value) if row is not None and row.value is not None else None,
                period=row.period if row is not None else None,
                source=row.source if row is not None else None,
                staleness=classify_staleness(row.ingested_at if row is not None else None),
            )
        )
    return tiles


def _fx_section(session: Session, iso3: str) -> FxDeltas | None:
    latest = get_latest_fx(session, iso3)
    if latest is None:
        return None
    deltas = compute_fx_deltas(session, iso3)
    return FxDeltas(
        latest=FxObservation(
            iso3=latest.iso3,
            ccy=latest.ccy,
            usd_per_ccy=float(latest.usd_per_ccy),
            observation_date=latest.observation_date,
            source=latest.source,
            ingested_at=latest.ingested_at,
        ),
        delta_1d_pct=deltas["delta_1d_pct"],
        delta_7d_pct=deltas["delta_7d_pct"],
        delta_30d_pct=deltas["delta_30d_pct"],
        delta_ytd_pct=deltas["delta_ytd_pct"],
    )


def _ratings_section(session: Session, iso3: str) -> RatingsSection:
    history = get_rating_history(session, iso3)
    latest_per_agency: dict[str, RatingAction] = {}
    for row in history:
        if row.agency not in latest_per_agency:
            latest_per_agency[row.agency] = RatingAction(
                iso3=row.iso3,
                agency=row.agency,
                rating=row.rating,
                outlook=row.outlook,
                action=row.action,
                action_date=row.action_date,
                source_url=row.source_url,
            )
    rating_dict = {a: r.rating for a, r in latest_per_agency.items()}
    return RatingsSection(
        latest_per_agency=latest_per_agency,
        composite_score=composite_score(rating_dict) if rating_dict else None,
        history=[
            RatingAction(
                iso3=r.iso3,
                agency=r.agency,
                rating=r.rating,
                outlook=r.outlook,
                action=r.action,
                action_date=r.action_date,
                source_url=r.source_url,
            )
            for r in history
        ],
    )


def _latest_approved_synopsis(session: Session, iso3: str) -> str | None:
    """Return the text of the latest approved synopsis, or None."""
    _approved = {"human_approved", "auto_approved_similarity", "auto_approved_stable_country"}
    row = (
        session.query(Synopsis)
        .filter(Synopsis.iso3 == iso3)
        .filter(Synopsis.approval_state.in_(_approved))
        .order_by(Synopsis.generated_at.desc())
        .first()
    )
    return row.text if row else None


def get_country_bundle(session: Session, iso3: str) -> CountryBundle | None:
    iso3 = iso3.upper()
    country = get_country(session, iso3)
    if country is None:
        return None

    macro = _macro_tiles(session, iso3)
    fx = _fx_section(session, iso3)
    ratings = _ratings_section(session, iso3)

    risk_indicators = {t.indicator.value: t.value for t in macro if t.value is not None}
    risk = compute_risk_score(
        status=country.status.value if hasattr(country.status, "value") else str(country.status),
        indicators=risk_indicators,
        fx_delta_30d_pct=fx.delta_30d_pct if fx is not None else None,
    )

    synopsis_text = _latest_approved_synopsis(session, iso3)

    # Enrich with forecasts
    forecasts = get_forecasts(session, iso3)
    if forecasts:
        country.forecasts = forecasts  # type: ignore[attr-defined]

    # Enrich with economic structure data
    econ = get_economic_structure(session, iso3)
    if econ:
        econ["diversification_score"] = country.economic_diversification_score
        econ["diversification_hhi"] = (
            float(country.economic_diversification_hhi)
            if country.economic_diversification_hhi
            else None
        )
        econ["commodity_dependency_pct"] = (
            float(country.commodity_dependency_pct) if country.commodity_dependency_pct else None
        )
        country.economic_structure = econ  # type: ignore[attr-defined]

    # Enrich with REER source info for the schema validator
    source_pref = ["imf_ifs", "bis_broad", "bis_narrow", "seed"]
    for src in source_pref:
        reer_row = session.execute(
            select(REERHistory)
            .where(REERHistory.iso3 == iso3, REERHistory.source == src)
            .order_by(REERHistory.period.desc())
            .limit(1)
        ).scalar_one_or_none()
        if reer_row:
            country.reer_source = reer_row.source  # type: ignore[attr-defined]
            country.reer_base_period = reer_row.base_period  # type: ignore[attr-defined]
            break

    return CountryBundle(
        country=CountrySchema.model_validate(country, from_attributes=True),
        macro=macro,
        fx=fx,
        ratings=ratings,
        risk=risk,
        synopsis=synopsis_text,
        news_placeholder=synopsis_text is None,
    )
