from atlas_schemas.bundle import CountryBundle
from atlas_schemas.country import Country as CountrySchema
from fastapi import APIRouter, HTTPException, status

from atlas_api.deps import CurrentUser, DbSession, _check_iso3
from atlas_api.services.country import get_country, list_countries
from atlas_api.services.country.bundle import get_country_bundle

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
