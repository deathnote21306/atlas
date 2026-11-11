"""State how deep Atlas coverage is for each country

PRD v2 CI-005 requires every country to be labeled Full Intelligence, Standard
Intelligence, Benchmark Data or Coming Soon. Until now all ten countries rendered at
visually equal depth despite carrying very different amounts of data, which implies
coverage the product does not have.

The ten seeded countries backfill to 'standard', not 'full': four of the eight pillars
CI-002 requires do not exist yet for any country, so none can honestly be Full. New
rows default to 'coming_soon'.

This is a separate axis from the existing `tier` column (A/B/C), which is market
tiering and is left untouched.

Revision ID: 0019_country_coverage_status
Revises: 0018_report_pdf_bytes
Create Date: 2026-11-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_country_coverage_status"
down_revision = "0018_report_pdf_bytes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "country",
        sa.Column(
            "coverage_status",
            sa.String(length=16),
            nullable=False,
            server_default="coming_soon",
        ),
    )
    op.execute("UPDATE country SET coverage_status = 'standard'")


def downgrade() -> None:
    op.drop_column("country", "coverage_status")
