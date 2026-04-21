import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
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

    # Phase 1 extensions
    iso_code_short: Mapped[str | None] = mapped_column(String(2), nullable=True)
    sub_region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status_tags: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    context_tags: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    composite_risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    composite_risk_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    composite_risk_trend: Mapped[str | None] = mapped_column(String(16), nullable=True)
    composite_risk_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    atlas_spread_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    atlas_spread_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    imf_program_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    imf_program_status: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Phase 2a extensions
    key_risks: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    key_opportunities: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    risk_decomposition: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    macro_annotations: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Phase 2b.1 — FX Intelligence
    primary_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    fx_change_1d_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    fx_change_1w_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    fx_change_1m_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    fx_change_3m_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    fx_change_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fx_implied_vol_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    fx_implied_vol_note: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fx_reer_deviation_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    fx_reer_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fx_last_bc_intervention: Mapped[datetime | None] = mapped_column(Date, nullable=True)

    # Phase 3a — Economic Structure
    economic_diversification_hhi: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    economic_diversification_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    economic_diversification_as_of: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commodity_dependency_pct: Mapped[float | None] = mapped_column(Numeric, nullable=True)


class TradeAnnual(Base):
    __tablename__ = "trade_annual"
    __table_args__ = (
        UniqueConstraint("reporter_iso3", "year", "flow", "partner_iso3", "commodity_code",
                        name="uq_trade_annual_row"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reporter_iso3: Mapped[str] = mapped_column(String(3), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    flow: Mapped[str] = mapped_column(String(2), nullable=False)
    partner_iso3: Mapped[str | None] = mapped_column(String(3), nullable=True)
    partner_name: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    commodity_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    commodity_label: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    trade_value_usd: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="comtrade")
    source_period: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), server_default=func.now()
    )


class REERHistory(Base):
    __tablename__ = "reer_history"
    __table_args__ = (
        UniqueConstraint("iso3", "period", "source", name="uq_reer_country_period_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    iso3: Mapped[str] = mapped_column(String(3), ForeignKey("country.iso3", ondelete="CASCADE"), nullable=False)
    period: Mapped[datetime] = mapped_column(Date, nullable=False)
    reer_index: Mapped[float] = mapped_column(Numeric, nullable=False)
    reer_deviation_pct: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    base_period: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_series_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), server_default=func.now()
    )


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
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        default=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        server_default=text("'00000000-0000-0000-0000-000000000000'::uuid"),
    )


class NewsItem(Base):
    __tablename__ = "news_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_iso3: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("country.iso3"), nullable=True
    )
    event_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    # Note: 'embedding' column is vector(384) managed via raw SQL in migration.
    # We do NOT map it here; we use raw queries for vector operations.


class NewsImpactScore(Base):
    __tablename__ = "news_impact_score"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    news_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("news_item.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    fiscal_impact: Mapped[str] = mapped_column(String(1), nullable=False)
    external_impact: Mapped[str] = mapped_column(String(1), nullable=False)
    fx_impact: Mapped[str] = mapped_column(String(1), nullable=False)
    political_impact: Mapped[str] = mapped_column(String(1), nullable=False)
    rationale: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    scorer: Mapped[str] = mapped_column(String(32), nullable=False)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    prompt_trace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_trace.id"), nullable=True
    )


class PromptTrace(Base):
    __tablename__ = "prompt_trace"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    approval_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class Synopsis(Base):
    __tablename__ = "synopsis"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iso3: Mapped[str] = mapped_column(String(3), ForeignKey("country.iso3"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    key_points: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    vintage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_vintage.id"), nullable=True
    )
    prompt_trace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_trace.id"), nullable=True
    )
    approval_state: Mapped[str] = mapped_column(
        String(40), nullable=False, default="proposed"
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        default=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        server_default=sa.text("'00000000-0000-0000-0000-000000000000'::uuid"),
    )
