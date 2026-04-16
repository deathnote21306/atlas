"""include source in uq_macro_vintage

Revision ID: 0005_uq_macro_vintage_add_source
Revises: 0004_ingestion_circuit
Create Date: 2026-04-16
"""
from __future__ import annotations

from alembic import op

revision = "0005_uq_macro_vintage_add_source"
down_revision = "0004_ingestion_circuit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_macro_vintage", "macro_indicator_vintage", type_="unique")
    op.create_unique_constraint(
        "uq_macro_vintage",
        "macro_indicator_vintage",
        ["iso3", "indicator", "period", "vintage_id", "source"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_macro_vintage", "macro_indicator_vintage", type_="unique")
    op.create_unique_constraint(
        "uq_macro_vintage",
        "macro_indicator_vintage",
        ["iso3", "indicator", "period", "vintage_id"],
    )
