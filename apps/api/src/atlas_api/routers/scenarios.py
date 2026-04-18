"""Scenario Engine API endpoints."""

from __future__ import annotations

import uuid

from atlas_schemas.scenario import CountryImpact, ScenarioPreview, ScenarioRunOut, ShockVector
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from atlas_api.deps import CurrentUser, DbSession, _check_iso3
from atlas_api.services.scenario.service import (
    get_scenario,
    list_scenarios,
    preview_all_countries,
    preview_scenario,
    save_scenario,
)

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


class PreviewRequest(BaseModel):
    iso3: str
    shocks: ShockVector


class SaveRequest(BaseModel):
    iso3: str
    shocks: ShockVector
    title: str = ""
    description: str | None = None


class PreviewAllRequest(BaseModel):
    shocks: ShockVector


@router.post("/preview-all", response_model=list[CountryImpact])
def preview_all(
    body: PreviewAllRequest,
    session: DbSession,
    _: CurrentUser,
) -> list[CountryImpact]:
    """Compute scenario preview for all countries, ranked by impact."""
    return preview_all_countries(session, body.shocks)


@router.post("/preview", response_model=ScenarioPreview)
def post_preview(
    body: PreviewRequest,
    session: DbSession,
    _: CurrentUser,
) -> ScenarioPreview:
    """Compute a scenario preview (no DB writes)."""
    body.iso3 = _check_iso3(body.iso3)
    try:
        return preview_scenario(session, body.iso3, body.shocks)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=ScenarioRunOut, status_code=status.HTTP_201_CREATED)
def post_save(
    body: SaveRequest,
    session: DbSession,
    user: CurrentUser,
) -> ScenarioRunOut:
    """Preview + persist a scenario run."""
    body.iso3 = _check_iso3(body.iso3)
    try:
        preview = preview_scenario(session, body.iso3, body.shocks)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return save_scenario(
        session, body.iso3, user.id, body.shocks, preview,
        title=body.title, description=body.description,
    )


@router.get("/{scenario_id}", response_model=ScenarioRunOut)
def get_one(
    scenario_id: uuid.UUID,
    session: DbSession,
    _: CurrentUser,
) -> ScenarioRunOut:
    """Retrieve a saved scenario by ID."""
    result = get_scenario(session, scenario_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"scenario {scenario_id} not found",
        )
    return result


@router.get("", response_model=list[ScenarioRunOut])
def list_all(
    session: DbSession,
    _: CurrentUser,
    iso3: str | None = Query(None, min_length=3, max_length=3, description="Country ISO3 code"),
) -> list[ScenarioRunOut]:
    """List saved scenarios, optionally filtered by country."""
    if iso3:
        iso3 = _check_iso3(iso3)
    return list_scenarios(session, iso3)
