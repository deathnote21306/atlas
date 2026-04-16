from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas_api.models import Country


def list_countries(session: Session) -> list[Country]:
    return list(session.execute(select(Country).order_by(Country.iso3)).scalars())


def get_country(session: Session, iso3: str) -> Country | None:
    return session.get(Country, iso3.upper())
