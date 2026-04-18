import re
from collections.abc import Iterator
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from atlas_api.db import get_session
from atlas_api.models import User
from atlas_api.security import InvalidTokenError, decode_access_token


def db_session() -> Iterator[Session]:
    yield from get_session()


DbSession = Annotated[Session, Depends(db_session)]


def get_current_user(
    session: DbSession,
    atlas_session: Annotated[str | None, Cookie()] = None,
) -> User:
    if atlas_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing session")
    try:
        payload = decode_access_token(atlas_session)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session"
        ) from exc
    user = session.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

_ISO3_RE = re.compile(r"^[A-Za-z]{3}$")


def _check_iso3(iso3: str) -> str:
    if not _ISO3_RE.match(iso3):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ISO3 code: {iso3}",
        )
    return iso3.upper()
