from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from atlas_api.db import get_session


def db_session() -> Iterator[Session]:
    yield from get_session()


DbSession = Depends(db_session)
