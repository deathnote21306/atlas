"""macro + fx + ratings

Revision ID: 0003_macro_fx_rating
Revises: 0002_country_and_vintage
Create Date: 2026-04-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0003_macro_fx_rating"
down_revision = "0002_country_and_vintage"
branch_labels = None
depends_on = None

AGENCIES = ("S&P", "Moodys", "Fitch")


def upgrade() -> None:
    op.create_table(
        "macro_indicator_vintage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("iso3", sa.String(3), sa.ForeignKey("country.iso3"), nullable=False),
        sa.Column("indicator", sa.String(64), nullable=False),
        sa.Column("value", sa.Numeric(20, 6), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_date", sa.Date, nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column(
            "vintage_id",
            UUID(as_uuid=True),
            sa.ForeignKey("data_vintage.id"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "iso3", "indicator", "period", "vintage_id", name="uq_macro_vintage"
        ),
    )
    op.create_index(
        "ix_macro_latest",
        "macro_indicator_vintage",
        ["iso3", "indicator", sa.text("period DESC"), sa.text("ingested_at DESC")],
    )

    op.create_table(
        "fx_rate",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("iso3", sa.String(3), sa.ForeignKey("country.iso3"), nullable=False),
        sa.Column("ccy", sa.String(3), nullable=False),
        sa.Column("usd_per_ccy", sa.Numeric(20, 8), nullable=False),
        sa.Column("observation_date", sa.Date, nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("iso3", "observation_date", name="uq_fx_daily"),
    )
    op.create_index(
        "ix_fx_iso3_date", "fx_rate", ["iso3", sa.text("observation_date DESC")]
    )

    op.create_table(
        "rating_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("iso3", sa.String(3), sa.ForeignKey("country.iso3"), nullable=False),
        sa.Column(
            "agency",
            sa.Enum(
                *AGENCIES,
                name="rating_agency",
                native_enum=False,
                length=16,
                create_constraint=True,
                validate_strings=True,
            ),
            nullable=False,
        ),
        sa.Column("rating", sa.String(16), nullable=False),
        sa.Column("outlook", sa.String(16), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("action_date", sa.Date, nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_rating_iso3_agency_date",
        "rating_history",
        ["iso3", "agency", sa.text("action_date DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_rating_iso3_agency_date", "rating_history")
    op.drop_table("rating_history")
    op.drop_index("ix_fx_iso3_date", "fx_rate")
    op.drop_table("fx_rate")
    op.drop_index("ix_macro_latest", "macro_indicator_vintage")
    op.drop_table("macro_indicator_vintage")
