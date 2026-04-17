"""add scenario_run table

Revision ID: 0006_scenario_run
Revises: 0005_uq_macro_vintage_add_source
Create Date: 2026-04-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0006_scenario_run"
down_revision = "0005_uq_macro_vintage_add_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenario_run",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "iso3", sa.String(3), sa.ForeignKey("country.iso3"),
            nullable=False,
        ),
        sa.Column(
            "input_vintage_id", UUID(as_uuid=True),
            sa.ForeignKey("data_vintage.id"), nullable=True,
        ),
        sa.Column("shocks", JSONB, nullable=False),
        sa.Column("outputs", JSONB, nullable=False),
        sa.Column(
            "created_by", UUID(as_uuid=True),
            sa.ForeignKey("user.id"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column("saved", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("'00000000-0000-0000-0000-000000000000'::uuid"),
        ),
    )
    op.create_index("ix_scenario_run_iso3", "scenario_run", ["iso3"])
    op.create_index("ix_scenario_run_created_by", "scenario_run", ["created_by"])
    op.create_index("ix_scenario_run_tenant_id", "scenario_run", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_scenario_run_tenant_id")
    op.drop_index("ix_scenario_run_created_by")
    op.drop_index("ix_scenario_run_iso3")
    op.drop_table("scenario_run")
