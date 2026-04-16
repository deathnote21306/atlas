"""Idempotently seed the single demo user from env vars."""

from sqlalchemy import select

from atlas_api.config import settings
from atlas_api.db import SessionLocal
from atlas_api.models import User
from atlas_api.security import hash_password


def main() -> None:
    with SessionLocal() as s:
        existing = s.execute(
            select(User).where(User.email == settings.demo_user_email)
        ).scalar_one_or_none()
        if existing is not None:
            print(f"demo user already exists: {settings.demo_user_email}")
            return
        u = User(
            email=settings.demo_user_email,
            password_hash=hash_password(settings.demo_user_password),
            role="Analyst",
        )
        s.add(u)
        s.commit()
        print(f"created demo user: {settings.demo_user_email}")


if __name__ == "__main__":
    main()
