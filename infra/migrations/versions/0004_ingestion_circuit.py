"""ingestion circuit breaker

Revision ID: 0004_ingestion_circuit
Revises: 0003_macro_fx_rating
Create Date: 2026-04-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_ingestion_circuit"
down_revision = "0003_macro_fx_rating"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_circuit",
        sa.Column("source", sa.String(32), primary_key=True),
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "state",
            sa.String(16),
            sa.CheckConstraint("state IN ('closed', 'open')", name="circuit_state_check"),
            nullable=False,
            server_default="closed",
        ),
    )


def downgrade() -> None:
    op.drop_table("ingestion_circuit")
