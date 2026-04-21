"""Add Phase 2a country fields: key_risks, key_opportunities, risk_decomposition, macro_annotations

Revision ID: 0011_country_phase2a_fields
Revises: 0010_country_phase1_fields
Create Date: 2026-04-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0011_country_phase2a_fields"
down_revision = "0010_country_phase1_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("country", sa.Column("key_risks", JSONB, nullable=True))
    op.add_column("country", sa.Column("key_opportunities", JSONB, nullable=True))
    op.add_column("country", sa.Column("risk_decomposition", JSONB, nullable=True))
    op.add_column("country", sa.Column("macro_annotations", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("country", "macro_annotations")
    op.drop_column("country", "risk_decomposition")
    op.drop_column("country", "key_opportunities")
    op.drop_column("country", "key_risks")
