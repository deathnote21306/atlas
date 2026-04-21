"""Add Phase 1 country intelligence fields

Revision ID: 0010_country_phase1_fields
Revises: 0009_ai_integration
Create Date: 2026-04-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010_country_phase1_fields"
down_revision = "0009_ai_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("country", sa.Column("iso_code_short", sa.String(2), nullable=True))
    op.add_column("country", sa.Column("sub_region", sa.String(100), nullable=True))
    op.add_column("country", sa.Column("status_tags", JSONB, nullable=True))
    op.add_column("country", sa.Column("context_tags", JSONB, nullable=True))

    op.add_column("country", sa.Column("composite_risk_score", sa.Integer, nullable=True))
    op.add_column("country", sa.Column("composite_risk_label", sa.String(32), nullable=True))
    op.add_column("country", sa.Column("composite_risk_trend", sa.String(16), nullable=True))
    op.add_column(
        "country",
        sa.Column("composite_risk_as_of", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column("country", sa.Column("atlas_spread_bps", sa.Integer, nullable=True))
    op.add_column(
        "country",
        sa.Column("atlas_spread_as_of", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column("country", sa.Column("imf_program_code", sa.String(8), nullable=True))
    op.add_column("country", sa.Column("imf_program_status", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("country", "imf_program_status")
    op.drop_column("country", "imf_program_code")
    op.drop_column("country", "atlas_spread_as_of")
    op.drop_column("country", "atlas_spread_bps")
    op.drop_column("country", "composite_risk_as_of")
    op.drop_column("country", "composite_risk_trend")
    op.drop_column("country", "composite_risk_label")
    op.drop_column("country", "composite_risk_score")
    op.drop_column("country", "context_tags")
    op.drop_column("country", "status_tags")
    op.drop_column("country", "sub_region")
    op.drop_column("country", "iso_code_short")
