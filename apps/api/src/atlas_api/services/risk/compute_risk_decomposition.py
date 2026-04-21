"""Compute risk decomposition for countries using deterministic formulas.

Merges computed scores/inputs with analyst-authored description/sub_drivers/warning.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy.orm import Session

from atlas_api.models import Country, REERHistory
from atlas_api.services.risk.formulas import (
    external_risk,
    fiscal_risk,
    fx_risk,
    growth_risk,
    liquidity_risk,
    political_risk,
)

log = structlog.get_logger()

SEED_PATH = Path(__file__).resolve().parents[6] / "infra" / "seed" / "risk_decomposition.json"

DIMENSION_ORDER = [
    ("fiscal", "Fiscal", 25),
    ("external", "External", 20),
    ("fx", "FX", 20),
    ("growth", "Growth", 15),
    ("political", "Political", 10),
    ("liquidity", "Liquidity", 10),
]

COMPOSITE_LABELS = [
    (85, "Severe Risk"),
    (70, "High Risk"),
    (50, "Elevated Risk"),
    (30, "Moderate Risk"),
    (0, "Low Risk"),
]


def _load_seed() -> dict[str, Any]:
    try:
        return dict(json.loads(SEED_PATH.read_text()))
    except FileNotFoundError:
        return {}


def _get_macro_value(session: Session, iso3: str, indicator: str) -> float | None:
    """Get latest non-null macro value for an indicator."""
    from sqlalchemy import select as sql_select

    from atlas_api.models import MacroIndicatorVintage

    row = session.execute(
        sql_select(MacroIndicatorVintage)
        .where(
            MacroIndicatorVintage.iso3 == iso3.upper(),
            MacroIndicatorVintage.indicator == indicator,
            MacroIndicatorVintage.value.isnot(None),
        )
        .order_by(MacroIndicatorVintage.period.desc(), MacroIndicatorVintage.ingested_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return float(row.value) if row and row.value is not None else None


def _get_reer_provenance(session: Session, iso3: str) -> str:
    from sqlalchemy import select

    row = session.execute(
        select(REERHistory.source)
        .where(REERHistory.iso3 == iso3)
        .order_by(REERHistory.period.desc())
        .limit(1)
    ).scalar()
    if row and row != "seed":
        return "real"
    return "seeded"


def compute_for_country(
    session: Session, country: Country, seed_data: dict[str, Any]
) -> dict[str, Any]:
    """Compute full risk decomposition for a single country."""
    iso3 = country.iso3
    now = datetime.now(UTC)

    si = seed_data.get("seeded_inputs", {})
    dim_seeds = seed_data.get("dimensions", {})

    # Gather inputs from DB
    fb = _get_macro_value(session, iso3, "FISCAL_BALANCE_PCT_GDP")
    ed = _get_macro_value(session, iso3, "EXTERNAL_DEBT_PCT_GNI")
    gdp_g = _get_macro_value(session, iso3, "GDP_GROWTH_PCT")
    reserves_months = _get_macro_value(session, iso3, "FX_RESERVES_MO_IMPORTS")

    pp = float(country.fx_parallel_premium) if country.fx_parallel_premium else 0
    reer = float(country.fx_reer_deviation_pct) if country.fx_reer_deviation_pct else 0
    iv = float(country.fx_implied_vol_pct) if country.fx_implied_vol_pct else None
    regime = (
        country.fx_regime.value if hasattr(country.fx_regime, "value") else str(country.fx_regime)
    )
    imf_active = country.imf_program_code is not None
    imf_type = country.imf_program_code
    pod = seed_data.get("pod_override_active", False)
    reserves_bn = None  # Not directly on country; would come from macro

    reer_prov = _get_reer_provenance(session, iso3)

    # Compute each dimension
    results = {}
    results["fiscal"] = fiscal_risk(fb, ed, si.get("revenue_quality_flag", "medium"))
    results["external"] = external_risk(
        reserves_months, si.get("external_restructuring_flag", False), pp, reserves_bn
    )
    results["fx"] = fx_risk(
        pp, reer, iv, regime, si.get("fx_market_liquidity_flag", "thin"), reer_prov
    )
    results["growth"] = growth_risk(
        gdp_g, si.get("gdp_volatility_5yr", 2.0), si.get("data_quality_flag", "medium")
    )
    results["political"] = political_risk(
        si.get("political_stability_index", 0.0), si.get("active_conflict_flag", False), imf_active
    )
    results["liquidity"] = liquidity_risk(
        si.get("market_access_flag", "limited"),
        reserves_bn,
        imf_type,
        si.get("restructuring_overhang_flag", False),
        pod,
    )

    # Build dimensions array
    dimensions = []
    total_weighted = 0
    total_weight = 0
    for key, label, weight in DIMENSION_ORDER:
        r = results[key]
        dim_seed = dim_seeds.get(key, {})
        dim = {
            "key": key,
            "label": label,
            "score": r["score"],
            "weight": weight,
            "edge_case": r["edge_case"],
            "description": dim_seed.get("description", ""),
            "sub_drivers": dim_seed.get("sub_drivers", []),
            "warning": dim_seed.get("warning"),
            "inputs": r["inputs"],
            "computed_at": now.isoformat(),
        }
        dimensions.append(dim)
        total_weighted += r["score"] * weight
        total_weight += weight

    composite = round(total_weighted / total_weight) if total_weight > 0 else 0
    composite_label = "Low Risk"
    for threshold, lbl in COMPOSITE_LABELS:
        if composite >= threshold:
            composite_label = lbl
            break

    return {
        "composite_score": composite,
        "composite_label": composite_label,
        "methodology_version": "v2.1",
        "pod_override_active": pod,
        "pod_override_reason": seed_data.get("pod_override_reason"),
        "dimensions": dimensions,
    }


def recompute_all(session: Session, countries: list[str] | None = None) -> dict[str, Any]:
    """Recompute risk decomposition for all (or specified) countries."""
    from sqlalchemy import select

    seed = _load_seed()
    if countries:
        rows: list[Country] = [
            c for iso3 in countries
            if (c := session.get(Country, iso3)) is not None
        ]
    else:
        rows = list(session.execute(select(Country).order_by(Country.iso3)).scalars())

    stats: dict[str, Any] = {"computed": 0, "errors": 0, "details": []}

    for country in rows:
        try:
            country_seed = seed.get(country.iso3, {})

            # Preserve analyst-authored fields from existing decomposition
            existing = country.risk_decomposition or {}
            result = compute_for_country(session, country, country_seed)

            # Merge: preserve description/sub_drivers/warning from existing if not in seed
            if existing.get("dimensions"):
                existing_by_key = {d["key"]: d for d in existing["dimensions"]}
                for dim in result["dimensions"]:
                    old = existing_by_key.get(dim["key"], {})
                    if not dim["description"] and old.get("description"):
                        dim["description"] = old["description"]
                    if not dim["sub_drivers"] and old.get("sub_drivers"):
                        dim["sub_drivers"] = old["sub_drivers"]
                    if dim["warning"] is None and old.get("warning"):
                        dim["warning"] = old["warning"]

            country.risk_decomposition = result
            country.composite_risk_score = result["composite_score"]
            country.composite_risk_label = result["composite_label"]
            country.composite_risk_as_of = datetime.now(UTC)

            stats["computed"] += 1
            stats["details"].append(
                {
                    "iso3": country.iso3,
                    "composite": result["composite_score"],
                    "label": result["composite_label"],
                }
            )
            log.info("risk_computed", iso3=country.iso3, composite=result["composite_score"])
        except Exception:
            log.exception("risk_compute_error", iso3=country.iso3)
            stats["errors"] += 1

    session.commit()
    return stats
