"""Add news relevance, translation and multi-country link

Revision ID: 0017_news_relevance
Revises: 0016_report
Create Date: 2026-08-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0017_news_relevance"
down_revision = "0016_report"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "news_item",
        sa.Column("relevant", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("news_item", sa.Column("relevance_score", sa.Integer(), nullable=True))
    op.add_column("news_item", sa.Column("relevance_rationale", sa.Text(), nullable=True))
    op.add_column("news_item", sa.Column("source_lang", sa.String(8), nullable=True))
    op.add_column("news_item", sa.Column("original_title", sa.Text(), nullable=True))
    op.add_column("news_item", sa.Column("summary_en", sa.Text(), nullable=True))
    op.add_column(
        "news_item",
        sa.Column("ai_graded", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "news_item",
        sa.Column(
            "prompt_trace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("prompt_trace.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_news_item_relevant", "news_item", ["relevant"])
    op.create_index("ix_news_item_relevance_score", "news_item", ["relevance_score"])

    op.create_table(
        "news_item_country",
        sa.Column(
            "news_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("news_item.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("iso3", sa.String(3), sa.ForeignKey("country.iso3"), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False, server_default="primary"),
    )
    op.create_index("ix_news_item_country_iso3", "news_item_country", ["iso3"])

    # Backfill links from the existing primary_iso3 so nothing is orphaned.
    op.execute(
        """
        INSERT INTO news_item_country (news_item_id, iso3, role)
        SELECT id, primary_iso3, 'primary' FROM news_item
        WHERE primary_iso3 IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_news_item_country_iso3", "news_item_country")
    op.drop_table("news_item_country")
    op.drop_index("ix_news_item_relevance_score", "news_item")
    op.drop_index("ix_news_item_relevant", "news_item")
    for col in (
        "prompt_trace_id",
        "ai_graded",
        "summary_en",
        "original_title",
        "source_lang",
        "relevance_rationale",
        "relevance_score",
        "relevant",
    ):
        op.drop_column("news_item", col)
