"""prompt_trace + synopsis tables

Revision ID: 0009_ai_integration
Revises: 0008_news_pipeline
Create Date: 2026-04-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0009_ai_integration"
down_revision = "0008_news_pipeline"
branch_labels = None
depends_on = None

APPROVAL_STATES = (
    "proposed", "human_approved", "auto_approved_similarity",
    "auto_approved_stable_country", "rejected",
)
PROMPT_PURPOSES = ("synopsis", "news_impact", "narrative_panel")


def upgrade() -> None:
    # -- prompt_trace --
    op.create_table(
        "prompt_trace",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("input", JSONB, nullable=False),
        sa.Column("output", JSONB, nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("approval_state", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_prompt_trace_purpose", "prompt_trace", ["purpose"])
    op.create_index("ix_prompt_trace_created_at", "prompt_trace", ["created_at"])

    # -- synopsis --
    op.create_table(
        "synopsis",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("iso3", sa.String(3), sa.ForeignKey("country.iso3"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("key_points", JSONB, nullable=False),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "vintage_id", UUID(as_uuid=True),
            sa.ForeignKey("data_vintage.id"), nullable=True,
        ),
        sa.Column(
            "prompt_trace_id", UUID(as_uuid=True),
            sa.ForeignKey("prompt_trace.id"), nullable=True,
        ),
        sa.Column(
            "approval_state", sa.String(40), nullable=False,
            server_default="proposed",
        ),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "tenant_id", UUID(as_uuid=True), nullable=False,
            server_default=sa.text("'00000000-0000-0000-0000-000000000000'::uuid"),
        ),
    )
    op.create_index("ix_synopsis_iso3", "synopsis", ["iso3"])
    op.create_index("ix_synopsis_approval_state", "synopsis", ["approval_state"])

    # Add prompt_trace_id FK to news_impact_score for AI scoring lineage
    op.add_column(
        "news_impact_score",
        sa.Column(
            "prompt_trace_id", UUID(as_uuid=True),
            sa.ForeignKey("prompt_trace.id"), nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("news_impact_score", "prompt_trace_id")
    op.drop_table("synopsis")
    op.drop_table("prompt_trace")
