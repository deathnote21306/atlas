"""Add report table

Revision ID: 0016_report
Revises: 0015_debt_profile
Create Date: 2026-06-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0016_report"
down_revision = "0015_debt_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("template", sa.String(64), nullable=False, server_default="country_brief"),
        sa.Column("iso3", sa.String(3), sa.ForeignKey("country.iso3"), nullable=False),
        sa.Column(
            "vintage_id", UUID(as_uuid=True), sa.ForeignKey("data_vintage.id"), nullable=True
        ),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("generated_by", UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("pdf_path", sa.String(512), nullable=True),
        sa.Column("manifest", JSONB, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
    )
    op.create_index("ix_report_iso3", "report", ["iso3"])
    op.create_index("ix_report_generated_at", "report", ["generated_at"])


def downgrade() -> None:
    op.drop_index("ix_report_generated_at", "report")
    op.drop_index("ix_report_iso3", "report")
    op.drop_table("report")
