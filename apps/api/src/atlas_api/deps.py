from collections.abc import Iterator

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from atlas_api.db import get_session
from atlas_api.models import User
from atlas_api.security import InvalidToken, decode_access_token


def db_session() -> Iterator[Session]:
    yield from get_session()


def get_current_user(
    session: Session = Depends(db_session),
    atlas_session: str | None = Cookie(default=None),
) -> User:
    if atlas_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing session")
    try:
        payload = decode_access_token(atlas_session)
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session"
        ) from exc
    user = session.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown user")
    return user
