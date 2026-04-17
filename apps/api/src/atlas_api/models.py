import uuid
from datetime import UTC, datetime
from typing import Any

from atlas_schemas.country import CountryStatus, FxRegime
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
        SqlEnum(
            CountryStatus,
            name="country_status",
            native_enum=False,
            length=32,
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    )
    fx_regime: Mapped[FxRegime] = mapped_column(
        SqlEnum(
            FxRegime,
            name="fx_regime",
            native_enum=False,
            length=32,
            values_callable=lambda enum: [e.value for e in enum],
        ),
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


class MacroIndicatorVintage(Base):
    __tablename__ = "macro_indicator_vintage"
    __table_args__ = (
        UniqueConstraint(
            "iso3", "indicator", "period", "vintage_id", "source", name="uq_macro_vintage"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iso3: Mapped[str] = mapped_column(String(3), ForeignKey("country.iso3"), nullable=False)
    indicator: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    vintage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_vintage.id"), nullable=False
    )


class FxRate(Base):
    __tablename__ = "fx_rate"
    __table_args__ = (UniqueConstraint("iso3", "observation_date", name="uq_fx_daily"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iso3: Mapped[str] = mapped_column(String(3), ForeignKey("country.iso3"), nullable=False)
    ccy: Mapped[str] = mapped_column(String(3), nullable=False)
    usd_per_ccy: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    observation_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class IngestionCircuit(Base):
    __tablename__ = "ingestion_circuit"

    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_failure_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="closed")


class RatingHistory(Base):
    __tablename__ = "rating_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iso3: Mapped[str] = mapped_column(String(3), ForeignKey("country.iso3"), nullable=False)
    agency: Mapped[str] = mapped_column(String(16), nullable=False)
    rating: Mapped[str] = mapped_column(String(16), nullable=False)
    outlook: Mapped[str | None] = mapped_column(String(16), nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    action_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class ScenarioRun(Base):
    __tablename__ = "scenario_run"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iso3: Mapped[str] = mapped_column(String(3), ForeignKey("country.iso3"), nullable=False)
    input_vintage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_vintage.id"), nullable=True
    )
    shocks: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    outputs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        default=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        server_default=text("'00000000-0000-0000-0000-000000000000'::uuid"),
    )
