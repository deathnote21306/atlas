from atlas_schemas.country import Country as CountrySchema
from fastapi import APIRouter, HTTPException, status

from atlas_api.deps import CurrentUser, DbSession
from atlas_api.services.country import get_country, list_countries

router = APIRouter(prefix="/api/countries", tags=["countries"])


@router.get("", response_model=list[CountrySchema])
def list_all(session: DbSession, _: CurrentUser) -> list[CountrySchema]:
    return [CountrySchema.model_validate(c, from_attributes=True) for c in list_countries(session)]


@router.get("/{iso3}", response_model=CountrySchema)
def get_one(iso3: str, session: DbSession, _: CurrentUser) -> CountrySchema:
    iso3 = iso3.upper()
    c = get_country(session, iso3)
    if c is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"country {iso3} not found",
        )
    return CountrySchema.model_validate(c, from_attributes=True)
