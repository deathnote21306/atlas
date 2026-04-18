from atlas_schemas.auth import LoginRequest, LoginResponse, Me
from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from atlas_api.config import settings
from atlas_api.deps import CurrentUser, DbSession
from atlas_api.models import User
from atlas_api.security import create_access_token, verify_password

router = APIRouter(prefix="/api", tags=["auth"])

COOKIE_NAME = "atlas_session"


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, response: Response, session: DbSession) -> LoginResponse:
    user = session.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    token = create_access_token(subject=str(user.id))
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=settings.jwt_expires_minutes * 60,
        path="/",
    )
    return LoginResponse(email=user.email, role=user.role)


@router.post("/auth/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        samesite="lax",
        secure=settings.is_production,
    )
    response.status_code = 204
    return response


@router.get("/me", response_model=Me)
def me(user: CurrentUser) -> Me:
    return Me(email=user.email, role=user.role)
