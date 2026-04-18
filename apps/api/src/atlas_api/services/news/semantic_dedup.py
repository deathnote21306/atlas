"""Semantic dedup via pgvector cosine similarity. Threshold >0.92 within 7-day window."""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

log = structlog.get_logger()

SIMILARITY_THRESHOLD = 0.92
WINDOW_DAYS = 7


def find_near_duplicates(
    session: Session,
    item_id: uuid.UUID,
    embedding: list[float],
    window_days: int = WINDOW_DAYS,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[uuid.UUID]:
    cutoff = datetime.now(UTC) - timedelta(days=window_days)
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
    rows = session.execute(
        text(
            "SELECT id FROM news_item "
            "WHERE embedding IS NOT NULL "
            "AND ingested_at > :cutoff "
            "AND id != :item_id "
            "AND 1 - (embedding <=> CAST(:vec AS vector)) > :threshold"
        ),
        {"cutoff": cutoff, "item_id": str(item_id), "vec": vec_str, "threshold": threshold},
    ).fetchall()
    return [uuid.UUID(str(r[0])) for r in rows]


def is_duplicate(
    session: Session,
    item_id: uuid.UUID,
    embedding: list[float],
) -> bool:
    dupes = find_near_duplicates(session, item_id, embedding)
    if dupes:
        log.info("semantic_duplicate_found", item_id=str(item_id), duplicate_of=str(dupes[0]))
    return len(dupes) > 0
