from atlas_schemas.bundle import CountryBundle
from atlas_schemas.country import Country as CountrySchema
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from atlas_api.deps import CurrentUser, DbSession, _check_iso3
from atlas_api.models import FxRate
from atlas_api.services.country import get_country, list_countries
from atlas_api.services.country.bundle import get_country_bundle
from atlas_api.services.country.indicators import ISO3_TO_CCY

router = APIRouter(prefix="/api/countries", tags=["countries"])


@router.get("", response_model=list[CountrySchema])
def list_all(session: DbSession, _: CurrentUser) -> list[CountrySchema]:
    return [CountrySchema.model_validate(c, from_attributes=True) for c in list_countries(session)]


@router.get("/{iso3}", response_model=CountrySchema)
def get_one(iso3: str, session: DbSession, _: CurrentUser) -> CountrySchema:
    iso3 = _check_iso3(iso3)
    c = get_country(session, iso3)
    if c is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"country {iso3} not found",
        )
    return CountrySchema.model_validate(c, from_attributes=True)


class FxHistoryPoint(BaseModel):
    date: str
    value: float
    source: str | None = None


class FxHistoryResponse(BaseModel):
    pair: str
    start: str
    end: str
    primary_source: str
    has_synthetic_data: bool
    points: list[FxHistoryPoint]


@router.get("/{iso3}/risk-decomposition/provenance")
def get_risk_provenance(iso3: str, session: DbSession, _: CurrentUser) -> dict:
    iso3 = _check_iso3(iso3)
    from atlas_api.services.country import get_country
    from atlas_api.services.risk.provenance import summarize_provenance
    c = get_country(session, iso3)
    if c is None:
        raise HTTPException(status_code=404, detail=f"country {iso3} not found")
    rd = c.risk_decomposition
    if not rd:
        return {"error": "risk decomposition not yet computed"}
    all_inputs = []
    for dim in rd.get("dimensions", []):
        all_inputs.extend(dim.get("inputs", []))
    summary = summarize_provenance(all_inputs)
    summary["composite_score"] = rd.get("composite_score")
    summary["methodology_version"] = rd.get("methodology_version")
    summary["computed_at"] = rd["dimensions"][0].get("computed_at") if rd.get("dimensions") else None
    return summary


@router.get("/{iso3}/fx-history")
def get_fx_history(
    iso3: str,
    session: DbSession,
    _: CurrentUser,
    window: str = Query("12m", pattern=r"^(3m|6m|12m|24m)$"),
) -> FxHistoryResponse:
    iso3 = _check_iso3(iso3)
    ccy = ISO3_TO_CCY.get(iso3)
    if not ccy:
        raise HTTPException(status_code=404, detail=f"No currency mapping for {iso3}")

    from datetime import date, timedelta
    months = {"3m": 90, "6m": 180, "12m": 365, "24m": 730}
    days_back = months[window]
    cutoff = date.today() - timedelta(days=days_back)

    rows = session.execute(
        select(FxRate)
        .where(FxRate.iso3 == iso3, FxRate.observation_date >= cutoff)
        .order_by(FxRate.observation_date.asc())
    ).scalars().all()

    points = []
    source_counts: dict[str, int] = {}
    has_synthetic = False
    for r in rows:
        usd_per_ccy = float(r.usd_per_ccy)
        if usd_per_ccy != 0:
            points.append(FxHistoryPoint(
                date=r.observation_date.isoformat(),
                value=round(1.0 / usd_per_ccy, 2),
                source=r.source,
            ))
            source_counts[r.source] = source_counts.get(r.source, 0) + 1
            if r.source in ("seed_approximation", "cfa_computed"):
                has_synthetic = True

    primary_source = max(source_counts, key=source_counts.get) if source_counts else "unknown"
    if len(source_counts) > 1 and source_counts.get(primary_source, 0) < len(points) * 0.8:
        primary_source = "mixed"

    return FxHistoryResponse(
        pair=f"USD/{ccy}",
        start=cutoff.isoformat(),
        end=date.today().isoformat(),
        primary_source=primary_source,
        has_synthetic_data=has_synthetic,
        points=points,
    )


@router.get("/{iso3}/bundle", response_model=CountryBundle)
def get_bundle(iso3: str, session: DbSession, _: CurrentUser) -> CountryBundle:
    iso3 = _check_iso3(iso3)
    bundle = get_country_bundle(session, iso3)
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"country {iso3} not found",
        )
    return bundle
