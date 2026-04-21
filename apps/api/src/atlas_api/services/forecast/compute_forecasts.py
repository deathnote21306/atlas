"""Forecast computation service — pulls IMF WEO baseline, computes bull/bear scenarios."""

from __future__ import annotations

from datetime import date
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas_api.models import Country, MacroIndicatorVintage
from atlas_api.services.forecast.scenarios import INDICATOR_CONFIG, compute_scenario

log = structlog.get_logger()


def _get_value_for_period(session: Session, iso3: str, indicator: str, period: str) -> float | None:
    row = session.execute(
        select(MacroIndicatorVintage.value)
        .where(
            MacroIndicatorVintage.iso3 == iso3,
            MacroIndicatorVintage.indicator == indicator,
            MacroIndicatorVintage.period == period,
            MacroIndicatorVintage.value.isnot(None),
        )
        .order_by(MacroIndicatorVintage.ingested_at.desc())
        .limit(1)
    ).scalar()
    return float(row) if row is not None else None


def _get_current_value(session: Session, iso3: str, indicator: str) -> float | None:
    """Get the most recent actual (non-projection) value."""
    current_year = date.today().year
    for yr in range(current_year, current_year - 3, -1):
        val = _get_value_for_period(session, iso3, indicator, str(yr))
        if val is not None:
            return val
    return None


def get_forecasts(session: Session, iso3: str) -> dict[str, Any] | None:
    country = session.get(Country, iso3)
    if country is None:
        return None

    current_year = date.today().year
    horizon_years = [current_year, current_year + 1]

    composite = country.composite_risk_score
    if composite is None:
        log.warning("forecast_no_composite_risk", iso3=iso3)
        risk_multiplier = 1.0
    else:
        risk_multiplier = round(composite / 50, 2)

    source_label = "IMF WEO" if risk_multiplier <= 1.2 else "IMF WEO / ATLAS (High Uncertainty)"

    indicators = []
    for cfg in INDICATOR_CONFIG:
        current_val = _get_current_value(session, iso3, cfg["db_key"])

        year_data = []
        for yr in horizon_years:
            baseline = _get_value_for_period(session, iso3, cfg["db_key"], str(yr))
            result = compute_scenario(
                baseline, cfg["base_width"], risk_multiplier,
                cfg["direction"], cfg["clamp"],
            )
            result["year"] = yr
            result["current_value"] = current_val if yr == current_year else None
            result["source"] = source_label if result["baseline_provenance"] == "real" else "Not available"
            year_data.append(result)

        indicators.append({
            "key": cfg["key"],
            "label": cfg["label"],
            "unit": cfg["unit"],
            "direction": cfg["direction"],
            "base_width": cfg["base_width"],
            "years": year_data,
        })

    return {
        "horizon_years": horizon_years,
        "current_year": current_year,
        "methodology_version": "v1.0",
        "methodology_note": f"Bull/Bear computed as baseline ± (base_width × composite_risk/50). Higher ATLAS risk produces wider uncertainty bands.",
        "risk_multiplier": risk_multiplier,
        "indicators": indicators,
    }
