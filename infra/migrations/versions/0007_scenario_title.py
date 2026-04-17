"""add title and description to scenario_run

Revision ID: 0007_scenario_title
Revises: 0006_scenario_run
Create Date: 2026-04-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_scenario_title"
down_revision = "0006_scenario_run"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scenario_run",
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
    )
    op.add_column(
        "scenario_run",
        sa.Column("description", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scenario_run", "description")
    op.drop_column("scenario_run", "title")
