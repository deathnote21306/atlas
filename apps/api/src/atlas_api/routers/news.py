"""News endpoints: list by country, get single item with impact score, admin scoring status."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from atlas_api.deps import CurrentUser, DbSession, _check_iso3
from atlas_api.models import NewsImpactScore, NewsItem, NewsItemCountry
from atlas_api.services.news.daily_rescore import get_scoring_status

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
        "summary_en": item.summary_en,
        "source_lang": item.source_lang,
        "relevance_score": item.relevance_score,
        "relevance_rationale": item.relevance_rationale,
        "translated": item.original_title is not None,
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
    stmt = (
        select(NewsItem, NewsImpactScore)
        .outerjoin(NewsImpactScore, NewsItem.id == NewsImpactScore.news_item_id)
        # Nothing is served until something has judged it relevant.
        .where(NewsItem.relevant.is_(True))
        .order_by(
            NewsItem.relevance_score.desc().nullslast(),
            NewsItem.published_at.desc(),
        )
    )
    if iso3:
        iso3 = _check_iso3(iso3)
        # Match primary or secondary, so an article covering two countries
        # appears on both feeds.
        stmt = stmt.join(NewsItemCountry, NewsItemCountry.news_item_id == NewsItem.id).where(
            NewsItemCountry.iso3 == iso3
        )
    rows = session.execute(stmt.limit(limit)).all()
    return [_item_to_out(item, score) for item, score in rows]


@router.get("/{news_id}")
def get_news_item(
    news_id: uuid.UUID,
    session: DbSession,
    _: CurrentUser,
) -> dict[str, Any]:
    stmt = (
        select(NewsItem, NewsImpactScore)
        .outerjoin(NewsImpactScore, NewsItem.id == NewsImpactScore.news_item_id)
        .where(NewsItem.id == news_id)
    )
    row = session.execute(stmt).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="news item not found")
    item, score = row
    return _item_to_out(item, score)


@router.get("/scoring-status")
def scoring_status(session: DbSession, _: CurrentUser) -> dict[str, Any]:
    return get_scoring_status(session)


@router.get("/reer-status")
def reer_status(session: DbSession, _: CurrentUser) -> dict[str, Any]:
    from sqlalchemy import func as sqlfunc

    from atlas_api.models import REERHistory

    rows = session.execute(
        select(
            REERHistory.iso3,
            sqlfunc.max(REERHistory.period).label("latest_period"),
            REERHistory.source,
        )
        .group_by(REERHistory.iso3, REERHistory.source)
        .order_by(REERHistory.iso3)
    ).all()

    seen: dict[str, dict[str, Any]] = {}
    for iso3, period, source in rows:
        if iso3 not in seen or source in ("imf_ifs",):
            dev = session.execute(
                select(REERHistory.reer_deviation_pct).where(
                    REERHistory.iso3 == iso3,
                    REERHistory.period == period,
                    REERHistory.source == source,
                )
            ).scalar()
            seen[iso3] = {
                "iso": iso3,
                "latest_period": str(period),
                "source": source,
                "deviation_pct": float(dev) if dev else None,
            }

    return {"coverage": list(seen.values())}
