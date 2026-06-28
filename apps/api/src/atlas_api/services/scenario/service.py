"""Scenario service -- orchestrates DB reads, engine calls, and persistence."""

from __future__ import annotations

import uuid

from atlas_schemas.scenario import CountryImpact, ScenarioPreview, ScenarioRunOut, ShockVector
from sqlalchemy.orm import Session

from atlas_api.models import ScenarioRun
from atlas_api.services.country.bundle import get_country_bundle
from atlas_api.services.scenario.engine import COUNTRY_COMMODITY_EXPOSURE, COMMODITY_SENSITIVITY, compute_scenario_preview


def preview_scenario(
    session: Session,
    iso3: str,
    shocks: ShockVector,
) -> ScenarioPreview:
    """Compute a scenario preview without persisting anything.

    Reads baseline data via the existing country bundle, then runs the shock
    engine in-memory. Target: <500ms.
    """
    iso3 = iso3.upper()
    bundle = get_country_bundle(session, iso3)
    if bundle is None:
        raise ValueError(f"Country {iso3} not found")

    # Extract baseline indicators from macro tiles
    baseline_indicators: dict[str, float] = {}
    for tile in bundle.macro:
        if tile.value is not None:
            baseline_indicators[tile.indicator.value] = tile.value

    # Extract baseline FX delta
    baseline_fx_delta = bundle.fx.delta_30d_pct if bundle.fx is not None else None

    # Extract status
    raw_status = bundle.country.status
    status = raw_status.value if hasattr(raw_status, "value") else str(raw_status)

    commodity_sensitivity = COUNTRY_COMMODITY_EXPOSURE.get(iso3, COMMODITY_SENSITIVITY)

    return compute_scenario_preview(
        status=status,
        baseline_indicators=baseline_indicators,
        baseline_fx_delta=baseline_fx_delta,
        shocks=shocks,
        baseline_risk_composite=bundle.risk.composite,
        commodity_sensitivity=commodity_sensitivity,
    )


def preview_all_countries(
    session: Session, shocks: ShockVector
) -> list[CountryImpact]:
    """Run scenario preview across all countries, return sorted by abs(risk_change) DESC."""
    from atlas_api.services.country.queries import list_countries

    results: list[CountryImpact] = []
    for country in list_countries(session):
        try:
            preview = preview_scenario(session, country.iso3, shocks)
        except ValueError:
            continue
        raw_status = country.status
        status = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
        results.append(CountryImpact(
            iso3=country.iso3,
            name=country.name,
            status=status,
            baseline_risk=preview.baseline_risk_score,
            new_risk=preview.new_risk_score,
            risk_change=round(preview.new_risk_score - preview.baseline_risk_score, 1),
            deltas=preview.deltas,
            distress_probability=preview.distress_probability,
        ))
    results.sort(key=lambda x: abs(x.risk_change), reverse=True)
    return results


def save_scenario(
    session: Session,
    iso3: str,
    user_id: uuid.UUID,
    shocks: ShockVector,
    preview: ScenarioPreview,
    *,
    title: str = "",
    description: str | None = None,
) -> ScenarioRunOut:
    """Persist a scenario run and return the saved record."""
    iso3 = iso3.upper()
    run = ScenarioRun(
        iso3=iso3,
        title=title,
        description=description,
        shocks=shocks.model_dump(),
        outputs=preview.model_dump(),
        created_by=user_id,
        saved=True,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    return ScenarioRunOut(
        id=run.id,
        iso3=run.iso3,
        title=run.title,
        description=run.description,
        shocks=ShockVector(**run.shocks),
        outputs=ScenarioPreview(**run.outputs),
        created_by=run.created_by,
        created_at=run.created_at,
        saved=run.saved,
    )


def get_scenario(session: Session, scenario_id: uuid.UUID) -> ScenarioRunOut | None:
    """Retrieve a single saved scenario by ID."""
    run = session.get(ScenarioRun, scenario_id)
    if run is None:
        return None
    return ScenarioRunOut(
        id=run.id,
        iso3=run.iso3,
        title=run.title,
        description=run.description,
        shocks=ShockVector(**run.shocks),
        outputs=ScenarioPreview(**run.outputs),
        created_by=run.created_by,
        created_at=run.created_at,
        saved=run.saved,
    )


def list_scenarios(session: Session, iso3: str | None = None) -> list[ScenarioRunOut]:
    """List all saved scenarios, optionally filtered by country, newest first."""
    from sqlalchemy import select

    stmt = select(ScenarioRun).where(ScenarioRun.saved.is_(True))
    if iso3 is not None:
        iso3 = iso3.upper()
        stmt = stmt.where(ScenarioRun.iso3 == iso3)
    stmt = stmt.order_by(ScenarioRun.created_at.desc())
    runs = list(session.execute(stmt).scalars())
    return [
        ScenarioRunOut(
            id=r.id,
            iso3=r.iso3,
            title=r.title,
            description=r.description,
            shocks=ShockVector(**r.shocks),
            outputs=ScenarioPreview(**r.outputs),
            created_by=r.created_by,
            created_at=r.created_at,
            saved=r.saved,
        )
        for r in runs
    ]
