"""Daily re-scoring job: converts heuristic-scored articles to Claude-scored.

Runs as a scheduled job, processes DAILY_RESCORE_LIMIT articles per run,
respecting DAILY_RESCORE_TOKEN_BUDGET.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from atlas_api.db import SessionLocal
from atlas_api.models import NewsImpactScore, NewsItem

log = structlog.get_logger()

DAILY_RESCORE_LIMIT = int(os.environ.get("DAILY_RESCORE_LIMIT", "50"))
DAILY_RESCORE_TOKEN_BUDGET = int(os.environ.get("DAILY_RESCORE_TOKEN_BUDGET", "150000"))


def run_daily_rescore() -> dict[str, Any]:
    """Re-score heuristic articles with Claude. Returns run stats."""
    stats = {
        "ran_at": datetime.now(UTC).isoformat(),
        "articles_processed": 0,
        "articles_succeeded": 0,
        "articles_failed": 0,
        "tokens_used": 0,
        "skipped_budget": False,
        "skipped_disabled": False,
    }

    if DAILY_RESCORE_LIMIT <= 0:
        stats["skipped_disabled"] = True
        log.info("daily_rescore_disabled", limit=DAILY_RESCORE_LIMIT)
        return stats

    session = SessionLocal()
    try:
        from atlas_api.services.ai.news_scorer import score_with_ai
        from atlas_api.services.ai.provider import token_counter
        from atlas_api.services.news.heuristic_scorer import persist_score, score_impact

        # Check if we already exceeded the daily cap
        if token_counter.is_exceeded():
            stats["skipped_budget"] = True
            log.info("daily_rescore_cap_exceeded")
            return stats

        # Get heuristic-scored articles, highest impact first
        rows = session.execute(
            select(NewsImpactScore, NewsItem)
            .join(NewsItem, NewsImpactScore.news_item_id == NewsItem.id)
            .where(NewsImpactScore.scorer == "heuristic")
            .order_by(NewsItem.published_at.desc().nullslast())
            .limit(DAILY_RESCORE_LIMIT)
        ).all()

        log.info("daily_rescore_start", candidates=len(rows), limit=DAILY_RESCORE_LIMIT)

        for score_row, item in rows:
            if int(stats["tokens_used"]) >= DAILY_RESCORE_TOKEN_BUDGET:
                log.info("daily_rescore_budget_reached", tokens=stats["tokens_used"])
                break

            stats["articles_processed"] += 1  # type: ignore[operator]

            # Delete existing heuristic score
            session.execute(delete(NewsImpactScore).where(NewsImpactScore.id == score_row.id))
            session.flush()

            try:
                ai_score = score_with_ai(
                    session,
                    news_item_id=item.id,
                    title=item.title,
                    body=item.body_text or "",
                    iso3=item.primary_iso3,
                    event_type=item.event_type,
                )

                if ai_score is not None:
                    stats["articles_succeeded"] += 1  # type: ignore[operator]
                    stats["tokens_used"] += 2000  # approximate  # type: ignore[operator]
                else:
                    # Claude unavailable — restore heuristic
                    scores = score_impact(item.title, item.body_text or "")
                    persist_score(session, item.id, scores)
                    stats["articles_failed"] += 1  # type: ignore[operator]
                    log.warning("daily_rescore_claude_unavailable", item_id=str(item.id))
            except Exception:
                # Restore heuristic on any error
                scores = score_impact(item.title, item.body_text or "")
                persist_score(session, item.id, scores)
                stats["articles_failed"] += 1  # type: ignore[operator]
                log.exception("daily_rescore_error", item_id=str(item.id))

            session.commit()

        log.info("daily_rescore_complete", **stats)
        return stats
    finally:
        session.close()


def get_scoring_status(session: Session) -> dict[str, Any]:
    """Return current scoring status for admin endpoint."""
    total = session.execute(select(func.count()).select_from(NewsImpactScore)).scalar() or 0
    claude_scored = (
        session.execute(select(func.count()).where(NewsImpactScore.scorer != "heuristic")).scalar()
        or 0
    )
    heuristic_scored = total - claude_scored

    return {
        "total_articles": total,
        "claude_scored": claude_scored,
        "heuristic_scored": heuristic_scored,
        "claude_scored_pct": round((claude_scored / total * 100) if total > 0 else 0, 1),
    }
