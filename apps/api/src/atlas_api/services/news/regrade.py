"""Re-grade articles already stored in the database.

The relevance migration hides every existing row. This restores the ones that
pass the new editorial bar and leaves the rest hidden but not deleted, so the
decision stays auditable and reversible.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas_api.config import settings
from atlas_api.models import NewsItem
from atlas_api.services.ai.provider import token_counter
from atlas_api.services.news.ai_grader import grade_article, passes_gate
from atlas_api.services.news.persist import apply_grade
from atlas_api.services.news.prefilter import is_obvious_junk

log = structlog.get_logger()


def regrade_batch(session: Session, limit: int) -> dict[str, int]:
    """Grade up to `limit` ungraded items. Safe to call repeatedly."""
    stats = {"seen": 0, "kept": 0, "rejected": 0, "junk": 0, "failed": 0}

    rows = list(
        session.execute(
            select(NewsItem)
            .where(NewsItem.ai_graded.is_(False))
            .order_by(NewsItem.published_at.desc().nullslast())
            .limit(limit)
        ).scalars()
    )

    for item in rows:
        stats["seen"] += 1

        if token_counter.is_exceeded():
            log.warning("regrade_stopped_token_cap", processed=stats["seen"] - 1)
            break

        if is_obvious_junk(item.title, item.body_text or ""):
            item.relevant = False
            item.ai_graded = True
            item.relevance_rationale = "Removed by the junk filter during backfill."
            stats["junk"] += 1
            session.commit()
            continue

        result, meta = grade_article(
            title=item.title,
            body=item.body_text or "",
            source=item.source,
            candidate_iso3=item.primary_iso3,
        )
        if result is None:
            stats["failed"] += 1
            continue

        keep = passes_gate(result, settings.news_relevance_threshold)
        apply_grade(session, item, result, meta, keep=keep)
        stats["kept" if keep else "rejected"] += 1
        session.commit()

    log.info("regrade_batch_complete", **stats)
    return stats
