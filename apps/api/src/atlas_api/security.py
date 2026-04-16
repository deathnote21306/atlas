from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from atlas_api.config import settings

_hasher = PasswordHasher()


class InvalidTokenError(Exception):
    """Raised when a JWT fails signature or expiry validation."""


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_expires_minutes))
    payload = {"sub": subject, "iat": int(now.timestamp()), "exp": int(expire.timestamp())}
    encoded: str = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded


def decode_access_token(token: str) -> dict[str, str | int]:
    try:
        decoded: dict[str, str | int] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    return decoded
