"""News pipeline orchestrator.

Chains: poll -> dedup -> embed -> semantic dedup -> NER -> classify -> score.
"""

from __future__ import annotations

import httpx
import structlog
from sqlalchemy import text

from atlas_api.db import SessionLocal
from atlas_api.services.news.dedup import store_new_articles
from atlas_api.services.news.embeddings import update_embeddings
from atlas_api.services.news.gdelt import poll_gdelt
from atlas_api.services.news.heuristic_scorer import persist_score, score_impact
from atlas_api.services.news.nlp import classify_event, extract_country, is_relevant
from atlas_api.services.news.rss import poll_rss
from atlas_api.services.news.semantic_dedup import is_duplicate

log = structlog.get_logger()


async def run_news_pipeline() -> dict[str, int]:
    """Run one poll cycle. Returns stats dict."""
    session = SessionLocal()
    stats = {"polled": 0, "stored": 0, "embedded": 0, "scored": 0, "irrelevant": 0, "duplicates": 0}
    try:
        # 1. Poll sources
        async with httpx.AsyncClient() as http:
            gdelt_articles = await poll_gdelt(http)
            rss_articles = await poll_rss(http)
        all_articles = gdelt_articles + rss_articles
        stats["polled"] = len(all_articles)

        # 2. URL dedup + store
        new_items = store_new_articles(session, all_articles)
        stats["stored"] = len(new_items)
        if not new_items:
            log.info("news_pipeline_no_new", **stats)
            return stats

        # 3. Generate embeddings
        embedded = update_embeddings(session, new_items)
        stats["embedded"] = embedded

        # 4. Process each item: semantic dedup → NER → relevance → classify → score
        for item in new_items:
            # Semantic dedup: fetch embedding from DB
            row = session.execute(
                text("SELECT embedding FROM news_item WHERE id = :id"),
                {"id": str(item.id)},
            ).first()
            embedding = row[0] if row and row[0] is not None else None
            if embedding is not None and is_duplicate(session, item.id, embedding):
                stats["duplicates"] += 1
                continue

            # NER: extract country
            iso3 = extract_country(item.title, item.body_text or "")
            if iso3:
                item.primary_iso3 = iso3
                session.commit()

            # Relevance filter
            if not is_relevant(item.title, item.body_text or ""):
                stats["irrelevant"] += 1
                continue

            # Event classification
            event_type = classify_event(item.title, item.body_text or "")
            item.event_type = event_type
            session.commit()

            # Heuristic impact scoring
            scores = score_impact(item.title, item.body_text or "")
            persist_score(session, item.id, scores)
            stats["scored"] += 1

        log.info("news_pipeline_complete", **stats)
        return stats
    except Exception:
        log.exception("news_pipeline_error")
        return stats
    finally:
        session.close()
