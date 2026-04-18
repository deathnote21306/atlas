"""news_item + news_impact_score tables

Revision ID: 0008_news_pipeline
Revises: 0007_scenario_title
Create Date: 2026-04-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0008_news_pipeline"
down_revision = "0007_scenario_title"
branch_labels = None
depends_on = None

EVENT_TYPES = ("Monetary", "Fiscal", "Political", "External", "Rating", "IMF", "Market")
IMPACT_LEVELS = ("L", "M", "H")


def upgrade() -> None:
    # -- news_item --
    op.create_table(
        "news_item",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.Text, nullable=False, unique=True),
        sa.Column("url_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("body_text", sa.Text, nullable=True),
        sa.Column(
            "primary_iso3",
            sa.String(3),
            sa.ForeignKey("country.iso3"),
            nullable=True,
        ),
        sa.Column(
            "event_type",
            sa.String(32),
            nullable=True,
        ),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            f"event_type IS NULL OR event_type IN ({', '.join(repr(e) for e in EVENT_TYPES)})",
            name="ck_news_item_event_type",
        ),
    )

    # Add vector column via raw SQL (pgvector)
    op.execute("ALTER TABLE news_item ADD COLUMN embedding vector(384)")

    # Composite index for country news feeds
    op.create_index(
        "ix_news_item_iso3_published",
        "news_item",
        ["primary_iso3", sa.text("published_at DESC")],
    )

    # HNSW index for semantic dedup
    op.execute(
        "CREATE INDEX ix_news_embedding ON news_item "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # -- news_impact_score --
    op.create_table(
        "news_impact_score",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "news_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("news_item.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("fiscal_impact", sa.String(1), nullable=False),
        sa.Column("external_impact", sa.String(1), nullable=False),
        sa.Column("fx_impact", sa.String(1), nullable=False),
        sa.Column("political_impact", sa.String(1), nullable=False),
        sa.Column("rationale", JSONB, nullable=True),
        sa.Column("scorer", sa.String(32), nullable=False),
        sa.Column(
            "scored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "fiscal_impact IN ('L', 'M', 'H')", name="ck_nis_fiscal"
        ),
        sa.CheckConstraint(
            "external_impact IN ('L', 'M', 'H')", name="ck_nis_external"
        ),
        sa.CheckConstraint(
            "fx_impact IN ('L', 'M', 'H')", name="ck_nis_fx"
        ),
        sa.CheckConstraint(
            "political_impact IN ('L', 'M', 'H')", name="ck_nis_political"
        ),
    )


def downgrade() -> None:
    op.drop_table("news_impact_score")
    op.execute("DROP INDEX IF EXISTS ix_news_embedding")
    op.drop_index("ix_news_item_iso3_published", table_name="news_item")
    op.drop_table("news_item")
