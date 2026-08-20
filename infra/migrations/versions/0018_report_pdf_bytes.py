"""Store generated report PDFs in the database

Container filesystems are ephemeral, so PDFs written to disk vanished on every
restart or redeploy and downloads began returning 410. Keeping the bytes on the
report row makes a generated brief durable. A brief is roughly 200 KB.

Revision ID: 0018_report_pdf_bytes
Revises: 0017_news_relevance
Create Date: 2026-08-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_report_pdf_bytes"
down_revision = "0017_news_relevance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("report", sa.Column("pdf_bytes", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("report", "pdf_bytes")
