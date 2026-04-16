"""country + data_vintage

Revision ID: 0002_country_and_vintage
Revises: 0001_baseline
Create Date: 2026-04-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "0002_country_and_vintage"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


COUNTRY_STATUS = ("performing", "negotiating", "selective_default", "default", "restructured")
FX_REGIME = (
    "float",
    "managed_float",
    "pegged",
    "crawling_peg",
    "basket_peg",
    "currency_board",
    "no_separate_legal_tender",
)


def upgrade() -> None:
    op.create_table(
        "country",
        sa.Column("iso3", sa.String(3), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("capital", sa.String(200), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("tags", ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("tier", sa.String(8), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            sa.CheckConstraint(f"status IN {COUNTRY_STATUS}", name="country_status_check"),
            nullable=False,
        ),
        sa.Column(
            "fx_regime",
            sa.String(32),
            sa.CheckConstraint(f"fx_regime IN {FX_REGIME}", name="country_fx_regime_check"),
            nullable=False,
        ),
        sa.Column("fx_regime_notes", sa.Text, nullable=True),
        sa.Column("fx_parallel_premium", sa.Float, nullable=True),
    )
    op.create_table(
        "data_vintage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_index("ix_data_vintage_created_at", "data_vintage", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_data_vintage_created_at", "data_vintage")
    op.drop_table("data_vintage")
    op.drop_table("country")
