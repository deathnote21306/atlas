"""Add Phase 2b.1 FX Intelligence fields to Country

Revision ID: 0012_fx_intelligence_fields
Revises: 0011_country_phase2a_fields
Create Date: 2026-04-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_fx_intelligence_fields"
down_revision = "0011_country_phase2a_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("country", sa.Column("primary_currency", sa.String(3), nullable=True))
    op.add_column("country", sa.Column("fx_change_1d_pct", sa.Numeric(10, 4), nullable=True))
    op.add_column("country", sa.Column("fx_change_1w_pct", sa.Numeric(10, 4), nullable=True))
    op.add_column("country", sa.Column("fx_change_1m_pct", sa.Numeric(10, 4), nullable=True))
    op.add_column("country", sa.Column("fx_change_3m_pct", sa.Numeric(10, 4), nullable=True))
    op.add_column(
        "country", sa.Column("fx_change_as_of", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("country", sa.Column("fx_implied_vol_pct", sa.Numeric(10, 4), nullable=True))
    op.add_column("country", sa.Column("fx_implied_vol_note", sa.String(32), nullable=True))
    op.add_column("country", sa.Column("fx_reer_deviation_pct", sa.Numeric(10, 4), nullable=True))
    op.add_column("country", sa.Column("fx_reer_as_of", sa.DateTime(timezone=True), nullable=True))
    op.add_column("country", sa.Column("fx_last_bc_intervention", sa.Date, nullable=True))


def downgrade() -> None:
    op.drop_column("country", "fx_last_bc_intervention")
    op.drop_column("country", "fx_reer_as_of")
    op.drop_column("country", "fx_reer_deviation_pct")
    op.drop_column("country", "fx_implied_vol_note")
    op.drop_column("country", "fx_implied_vol_pct")
    op.drop_column("country", "fx_change_as_of")
    op.drop_column("country", "fx_change_3m_pct")
    op.drop_column("country", "fx_change_1m_pct")
    op.drop_column("country", "fx_change_1w_pct")
    op.drop_column("country", "fx_change_1d_pct")
    op.drop_column("country", "primary_currency")
