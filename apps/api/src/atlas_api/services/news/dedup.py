"""URL-hash dedup and initial article storage."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas_api.models import NewsItem
from atlas_api.services.news import RawArticle

log = structlog.get_logger()


def url_hash(url: str) -> str:
    """SHA-256 hash of the normalized URL."""
    normalized = url.strip().lower().rstrip("/")
    return hashlib.sha256(normalized.encode()).hexdigest()


def get_existing_url_hashes(session: Session, days: int = 30) -> set[str]:
    """Load URL hashes from the last N days for fast dedup lookups."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    stmt = select(NewsItem.url_hash).where(NewsItem.ingested_at >= cutoff)
    return set(session.scalars(stmt).all())


def store_new_articles(
    session: Session,
    articles: list[RawArticle],
    existing_hashes: set[str] | None = None,
) -> list[NewsItem]:
    """Insert new articles into news_item. Returns list of newly inserted rows."""
    if existing_hashes is None:
        existing_hashes = get_existing_url_hashes(session)

    new_items: list[NewsItem] = []
    skipped = 0

    for art in articles:
        h = url_hash(art.url)
        if h in existing_hashes:
            skipped += 1
            continue
        existing_hashes.add(h)  # prevent intra-batch dupes

        item = NewsItem(
            id=uuid.uuid4(),
            url=art.url,
            url_hash=h,
            title=art.title,
            source=art.source,
            published_at=art.published_at,
            body_text=art.body_snippet if art.body_snippet else None,
            raw_payload={"source_feed": art.source_feed},
        )
        session.add(item)
        new_items.append(item)

    if new_items:
        session.commit()

    log.info("url_dedup_complete", new=len(new_items), skipped=skipped)
    return new_items
