import uuid
from datetime import UTC, datetime

from atlas_schemas.country import CountryStatus, FxRegime
from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import ARRAY

from atlas_api.db import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="Analyst")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class Country(Base):
    __tablename__ = "country"

    iso3: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    capital: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    tier: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[CountryStatus] = mapped_column(
        SqlEnum(CountryStatus, name="country_status", native_enum=False, length=32),
        nullable=False,
    )
    fx_regime: Mapped[FxRegime] = mapped_column(
        SqlEnum(FxRegime, name="fx_regime", native_enum=False, length=32),
        nullable=False,
    )
    fx_regime_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    fx_parallel_premium: Mapped[float | None] = mapped_column(Float, nullable=True)


class DataVintage(Base):
    __tablename__ = "data_vintage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
