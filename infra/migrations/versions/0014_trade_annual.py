"""Add trade_annual table and economic diversification fields on Country

Revision ID: 0014_trade_annual
Revises: 0013_reer_history
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_trade_annual"
down_revision = "0013_reer_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trade_annual",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("reporter_iso3", sa.String(3), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("flow", sa.String(2), nullable=False),
        sa.Column("partner_iso3", sa.String(3), nullable=True),
        sa.Column("partner_name", sa.String, nullable=True),
        sa.Column("commodity_code", sa.String(10), nullable=True),
        sa.Column("commodity_label", sa.String, nullable=True),
        sa.Column("trade_value_usd", sa.BigInteger, nullable=True),
        sa.Column("quantity", sa.Numeric, nullable=True),
        sa.Column("quantity_unit", sa.String, nullable=True),
        sa.Column("source", sa.String, server_default="comtrade"),
        sa.Column("source_period", sa.String, nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "reporter_iso3",
            "year",
            "flow",
            "partner_iso3",
            "commodity_code",
            name="uq_trade_annual_row",
        ),
    )
    op.create_index(
        "ix_trade_annual_reporter_year", "trade_annual", ["reporter_iso3", sa.text("year DESC")]
    )
    op.create_index("ix_trade_annual_partner", "trade_annual", ["partner_iso3"])
    op.create_index("ix_trade_annual_commodity", "trade_annual", ["commodity_code"])

    op.add_column("country", sa.Column("economic_diversification_hhi", sa.Numeric, nullable=True))
    op.add_column("country", sa.Column("economic_diversification_score", sa.Integer, nullable=True))
    op.add_column("country", sa.Column("economic_diversification_as_of", sa.Integer, nullable=True))
    op.add_column("country", sa.Column("commodity_dependency_pct", sa.Numeric, nullable=True))


def downgrade() -> None:
    op.drop_column("country", "commodity_dependency_pct")
    op.drop_column("country", "economic_diversification_as_of")
    op.drop_column("country", "economic_diversification_score")
    op.drop_column("country", "economic_diversification_hhi")
    op.drop_table("trade_annual")
