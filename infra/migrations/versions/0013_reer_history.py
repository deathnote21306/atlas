"""Add reer_history table

Revision ID: 0013_reer_history
Revises: 0012_fx_intelligence_fields
Create Date: 2026-04-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_reer_history"
down_revision = "0012_fx_intelligence_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reer_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "iso3", sa.String(3), sa.ForeignKey("country.iso3", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("period", sa.Date, nullable=False),
        sa.Column("reer_index", sa.Numeric, nullable=False),
        sa.Column("reer_deviation_pct", sa.Numeric, nullable=True),
        sa.Column("base_period", sa.String(32), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_series_id", sa.String(128), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("iso3", "period", "source", name="uq_reer_country_period_source"),
    )
    op.create_index("ix_reer_history_iso3_period", "reer_history", ["iso3", sa.text("period DESC")])


def downgrade() -> None:
    op.drop_table("reer_history")
