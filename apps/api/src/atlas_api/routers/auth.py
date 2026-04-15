from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas_api.config import settings
from atlas_api.deps import db_session, get_current_user
from atlas_api.models import User
from atlas_api.security import create_access_token, verify_password
from atlas_schemas.auth import LoginRequest, LoginResponse, Me

router = APIRouter(prefix="/api", tags=["auth"])

COOKIE_NAME = "atlas_session"


@router.post("/auth/login", response_model=LoginResponse)
def login(
    body: LoginRequest, response: Response, session: Session = Depends(db_session)
) -> LoginResponse:
    user = session.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    token = create_access_token(subject=str(user.id))
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.jwt_expires_minutes * 60,
        path="/",
    )
    return LoginResponse(email=user.email, role=user.role)


@router.get("/me", response_model=Me)
def me(user: User = Depends(get_current_user)) -> Me:
    return Me(email=user.email, role=user.role)
