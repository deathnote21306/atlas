"""Add debt_profile JSONB column to country

Revision ID: 0015_debt_profile
Revises: 0014_trade_annual
Create Date: 2026-06-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0015_debt_profile"
down_revision = "0014_trade_annual"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("country", sa.Column("debt_profile", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("country", "debt_profile")
