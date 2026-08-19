"""Write a graded article: flags, translation, country links, impact score, trace."""

from __future__ import annotations

from typing import Any

import structlog
from atlas_schemas.ai import NewsGradeResult
from sqlalchemy.orm import Session

from atlas_api.models import NewsItem, NewsItemCountry
from atlas_api.services.ai.trace import persist_trace
from atlas_api.services.news.heuristic_scorer import persist_score

log = structlog.get_logger()


def apply_grade(
    session: Session,
    item: NewsItem,
    result: NewsGradeResult,
    meta: dict[str, Any],
    *,
    keep: bool,
) -> None:
    """Apply a grade to an item. Writes links and score only when the item is kept."""
    trace = persist_trace(
        session,
        purpose="news_impact",
        model=meta.get("model", ""),
        prompt_hash=meta.get("prompt_hash", ""),
        input_hash=meta.get("input_hash", ""),
        input_data={"title": item.title},
        output_data=result.model_dump(),
        tokens_in=meta.get("tokens_in", 0),
        tokens_out=meta.get("tokens_out", 0),
    )

    item.ai_graded = True
    item.prompt_trace_id = trace.id
    item.relevance_score = result.relevance_score
    item.relevance_rationale = result.rationale
    item.source_lang = result.source_lang
    item.summary_en = result.summary_en
    item.event_type = result.event_type
    item.relevant = keep

    # Preserve the source title only when a translation actually replaced it.
    if result.title_en and result.title_en != item.title:
        item.original_title = item.title
        item.title = result.title_en

    if not keep:
        log.info(
            "news_item_rejected",
            score=result.relevance_score,
            reason=result.rationale[:120],
        )
        return

    item.primary_iso3 = result.primary_iso3

    session.merge(
        NewsItemCountry(news_item_id=item.id, iso3=result.primary_iso3, role="primary")
    )
    for iso3 in result.secondary_iso3:
        if iso3 != result.primary_iso3:
            session.merge(NewsItemCountry(news_item_id=item.id, iso3=iso3, role="secondary"))

    persist_score(
        session,
        item.id,
        {
            "fiscal_impact": result.fiscal_impact,
            "external_impact": result.external_impact,
            "fx_impact": result.fx_impact,
            "political_impact": result.political_impact,
            "rationale": {"grade": result.rationale},
        },
        scorer="ai_grader",
    )


def mark_deferred(session: Session, item: NewsItem) -> None:
    """Leave an item ungraded and unserved so a later run can pick it up."""
    item.relevant = False
    item.ai_graded = False
