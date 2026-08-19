"""News pipeline orchestrator.

Chains: poll -> store -> embed -> semantic dedup -> junk cut -> budget split ->
AI grade -> persist. Grading is blocking, so it is offloaded to a worker thread:
this coroutine is run directly on the event loop by the scheduler and must never
block it.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from atlas_api.config import settings
from atlas_api.db import SessionLocal
from atlas_api.services.news.ai_grader import grade_article, passes_gate
from atlas_api.services.news.dedup import store_new_articles
from atlas_api.services.news.embeddings import update_embeddings
from atlas_api.services.news.gdelt import poll_gdelt
from atlas_api.services.news.heuristic_scorer import persist_score, score_impact
from atlas_api.services.news.nlp import classify_event, extract_country, is_relevant
from atlas_api.services.news.persist import apply_grade, mark_deferred
from atlas_api.services.news.prefilter import TRACKED_ISO3, is_obvious_junk, split_by_budget
from atlas_api.services.news.rss import poll_rss
from atlas_api.services.news.semantic_dedup import is_duplicate

log = structlog.get_logger()


def _heuristic_fallback(session: Session, item: Any) -> bool:
    """Used when the AI is unavailable. Keeps the feed alive during an outage.

    Returns True when the item is kept.
    """
    title = item.title
    body = item.body_text or ""
    iso3 = extract_country(title, body)
    keep = bool(iso3) and iso3 in TRACKED_ISO3 and is_relevant(title, body)

    item.ai_graded = False
    item.relevant = keep
    if not keep:
        return False

    item.primary_iso3 = iso3
    item.event_type = classify_event(title, body)
    item.relevance_rationale = "Scored by keyword fallback while the AI was unavailable."
    persist_score(session, item.id, score_impact(title, body))
    return True


async def run_news_pipeline() -> dict[str, int]:
    """Run one poll cycle. Returns stats dict."""
    session = SessionLocal()
    stats: dict[str, int] = {
        "polled": 0,
        "stored": 0,
        "embedded": 0,
        "duplicates": 0,
        "junk": 0,
        "graded": 0,
        "kept": 0,
        "rejected": 0,
        "deferred": 0,
        "heuristic_fallback": 0,
    }
    try:
        async with httpx.AsyncClient() as http:
            gdelt_articles = await poll_gdelt(http)
            rss_articles = await poll_rss(http)
        all_articles = gdelt_articles + rss_articles
        stats["polled"] = len(all_articles)

        new_items = store_new_articles(session, all_articles)
        stats["stored"] = len(new_items)
        if not new_items:
            log.info("news_pipeline_no_new", **stats)
            return stats

        stats["embedded"] = update_embeddings(session, new_items)

        # Cheap filters first so nothing junk or duplicated is ever paid for.
        candidates = []
        for item in new_items:
            row = session.execute(
                text("SELECT embedding FROM news_item WHERE id = :id"),
                {"id": str(item.id)},
            ).first()
            embedding = row[0] if row and row[0] is not None else None
            if embedding is not None and is_duplicate(session, item.id, embedding):
                stats["duplicates"] += 1
                continue
            if is_obvious_junk(item.title, item.body_text or ""):
                stats["junk"] += 1
                continue
            candidates.append(item)

        to_grade, deferred = split_by_budget(candidates, settings.news_ai_calls_per_run)
        for item in deferred:
            mark_deferred(session, item)
        stats["deferred"] = len(deferred)
        session.commit()

        for item in to_grade:
            candidate_iso3 = extract_country(item.title, item.body_text or "")
            # Blocking Anthropic call. Never run this on the event loop.
            result, meta = await asyncio.to_thread(
                grade_article,
                title=item.title,
                body=item.body_text or "",
                source=item.source,
                candidate_iso3=candidate_iso3,
            )

            if result is None:
                if _heuristic_fallback(session, item):
                    stats["kept"] += 1
                else:
                    stats["rejected"] += 1
                stats["heuristic_fallback"] += 1
                session.commit()
                continue

            keep = passes_gate(result, settings.news_relevance_threshold)
            apply_grade(session, item, result, meta, keep=keep)
            stats["graded"] += 1
            stats["kept" if keep else "rejected"] += 1
            session.commit()

        log.info("news_pipeline_complete", **stats)
        return stats
    except Exception:
        log.exception("news_pipeline_error")
        return stats
    finally:
        session.close()
