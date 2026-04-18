"""Claude-based 4-axis news impact scorer.

Falls back to heuristic scorer on:
- API key not configured
- Daily token cap exceeded
- Claude API error after retry
- Schema validation failure after retry
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from atlas_schemas.ai import AIScoreResult
from sqlalchemy.orm import Session

from atlas_api.config import settings
from atlas_api.models import NewsImpactScore
from atlas_api.services.ai.provider import call_tool, compute_input_hash
from atlas_api.services.ai.trace import persist_trace
from atlas_api.services.news.heuristic_scorer import (
    persist_score as persist_heuristic_score,
)
from atlas_api.services.news.heuristic_scorer import (
    score_impact as heuristic_score,
)

log = structlog.get_logger()

_SYSTEM_PROMPT = """You are a sovereign-finance analyst specialising in African economies.
You assess news articles for their impact on a country's sovereign risk profile.

Score each article across 4 axes using L (low), M (medium), or H (high):
- fiscal_impact: Effect on government budget, debt, fiscal position
- external_impact: Effect on trade balance, FDI, external financing
- fx_impact: Effect on exchange rate, reserves, currency stability
- political_impact: Effect on political stability, governance, reform trajectory

Provide a brief rationale for each axis score."""


def _build_messages(
    title: str, body: str, iso3: str | None, event_type: str | None,
) -> list[dict[str, Any]]:
    context_parts = [f"Title: {title}"]
    if body:
        # Truncate body to ~2000 chars to manage token usage
        context_parts.append(f"Body: {body[:2000]}")
    if iso3:
        context_parts.append(f"Country: {iso3}")
    if event_type:
        context_parts.append(f"Event type: {event_type}")

    return [{"role": "user", "content": "\n\n".join(context_parts)}]


def score_with_ai(
    session: Session,
    *,
    news_item_id: uuid.UUID,
    title: str,
    body: str,
    iso3: str | None = None,
    event_type: str | None = None,
) -> NewsImpactScore | None:
    """Score a news item using Claude. Returns the persisted score, or None if AI unavailable.

    On None return, the caller should fall back to heuristic scoring.
    """
    if not settings.anthropic_api_key:
        log.debug("ai_scorer_no_api_key")
        return None

    messages = _build_messages(title, body, iso3, event_type)
    grounding_data = {"title": title, "body": body[:500], "iso3": iso3, "event_type": event_type}
    input_hash = compute_input_hash(grounding_data)

    result, meta = call_tool(
        messages=messages,
        system=_SYSTEM_PROMPT,
        tool_name="score_news_impact",
        tool_description="Score a news article's impact on sovereign risk across 4 axes",
        result_model=AIScoreResult,
        max_tokens=1024,
    )

    if result is None:
        log.info("ai_scorer_fallback", reason=meta.get("error"), news_item_id=str(news_item_id))
        return None

    # Persist trace
    trace = persist_trace(
        session,
        purpose="news_impact",
        model=meta["model"],
        prompt_hash=meta["prompt_hash"],
        input_hash=input_hash,
        input_data={"system": _SYSTEM_PROMPT, "messages": messages},
        output_data=result.model_dump(),
        tokens_in=meta["tokens_in"],
        tokens_out=meta["tokens_out"],
    )

    # Persist score
    row = NewsImpactScore(
        id=uuid.uuid4(),
        news_item_id=news_item_id,
        fiscal_impact=result.fiscal_impact,
        external_impact=result.external_impact,
        fx_impact=result.fx_impact,
        political_impact=result.political_impact,
        rationale=result.rationale,
        scorer=meta["model"],
        scored_at=datetime.now(UTC),
        prompt_trace_id=trace.id,
    )
    session.add(row)
    session.flush()
    return row


def score_news_item(
    session: Session,
    *,
    news_item_id: uuid.UUID,
    title: str,
    body: str,
    iso3: str | None = None,
    event_type: str | None = None,
) -> NewsImpactScore:
    """Score a news item: try AI first, fall back to heuristic.

    Always returns a persisted score — never None.
    """
    ai_score = score_with_ai(
        session,
        news_item_id=news_item_id,
        title=title, body=body,
        iso3=iso3, event_type=event_type,
    )
    if ai_score is not None:
        return ai_score

    # Heuristic fallback
    score_dict = heuristic_score(title, body)
    return persist_heuristic_score(session, news_item_id, score_dict)
