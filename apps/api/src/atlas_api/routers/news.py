"""News endpoints: list by country, get single item with impact score."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from atlas_api.deps import CurrentUser, DbSession, _check_iso3
from atlas_api.models import NewsImpactScore, NewsItem

router = APIRouter(prefix="/api/news", tags=["news"])


def _item_to_out(item: NewsItem, score: NewsImpactScore | None = None) -> dict[str, Any]:
    out = {
        "id": item.id,
        "url": item.url,
        "title": item.title,
        "source": item.source,
        "published_at": item.published_at,
        "body_text": (item.body_text or "")[:500],
        "primary_iso3": item.primary_iso3,
        "event_type": item.event_type,
        "ingested_at": item.ingested_at,
    }
    if score:
        out["score"] = {
            "fiscal_impact": score.fiscal_impact,
            "external_impact": score.external_impact,
            "fx_impact": score.fx_impact,
            "political_impact": score.political_impact,
            "rationale": score.rationale,
            "scorer": score.scorer,
            "scored_at": score.scored_at,
        }
    return out


@router.get("")
def list_news(
    session: DbSession,
    _: CurrentUser,
    iso3: str | None = Query(None),
    limit: int = Query(30, ge=1, le=100),
) -> list[dict[str, Any]]:
    stmt = select(NewsItem, NewsImpactScore).outerjoin(
        NewsImpactScore, NewsItem.id == NewsImpactScore.news_item_id
    ).order_by(NewsItem.published_at.desc()).limit(limit)
    if iso3:
        iso3 = _check_iso3(iso3)
        stmt = stmt.where(NewsItem.primary_iso3 == iso3)
    rows = session.execute(stmt).all()
    return [_item_to_out(item, score) for item, score in rows]


@router.get("/{news_id}")
def get_news_item(
    news_id: uuid.UUID,
    session: DbSession,
    _: CurrentUser,
) -> dict[str, Any]:
    stmt = select(NewsItem, NewsImpactScore).outerjoin(
        NewsImpactScore, NewsItem.id == NewsImpactScore.news_item_id
    ).where(NewsItem.id == news_id)
    row = session.execute(stmt).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="news item not found")
    item, score = row
    return _item_to_out(item, score)
