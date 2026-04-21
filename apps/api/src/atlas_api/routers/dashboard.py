"""Dashboard aggregate endpoints — portfolio-level summaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import select

from atlas_api.deps import CurrentUser, DbSession
from atlas_api.models import (
    Country,
    MacroIndicatorVintage,
    NewsImpactScore,
    NewsItem,
    RatingHistory,
)
from atlas_api.services.country.staleness import classify_staleness

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

WATCH_TAGS = {"DISTRESSED", "RESTRUCTURING", "WATCHLIST"}

COMPOSITE_LABELS = [
    (85, "Severe Risk"),
    (70, "High Risk"),
    (50, "Elevated Risk"),
    (30, "Moderate Risk"),
    (0, "Low Risk"),
]


def _label(score: int) -> str:
    for threshold, label in COMPOSITE_LABELS:
        if score >= threshold:
            return label
    return "Low Risk"


@router.get("/summary")
def dashboard_summary(session: DbSession, _: CurrentUser) -> dict[str, Any]:
    countries = list(session.execute(select(Country).order_by(Country.iso3)).scalars())

    # Countries under watch
    elevated = [
        c for c in countries if c.status_tags and any(t in WATCH_TAGS for t in c.status_tags)
    ]

    # Portfolio risk
    scores = [c.composite_risk_score for c in countries if c.composite_risk_score is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    # Staleness index
    indicators = [
        "GDP_GROWTH_PCT",
        "INFLATION_PCT",
        "FISCAL_BALANCE_PCT_GDP",
        "CURRENT_ACCOUNT_PCT_GDP",
        "PUBLIC_DEBT_PCT_GDP",
        "EXTERNAL_DEBT_PCT_GNI",
        "FX_RESERVES_MO_IMPORTS",
    ]
    fresh = 0
    stale = 0
    very_stale = 0
    total_ind = 0
    for c in countries:
        for ind in indicators:
            total_ind += 1
            row = session.execute(
                select(MacroIndicatorVintage.ingested_at)
                .where(
                    MacroIndicatorVintage.iso3 == c.iso3,
                    MacroIndicatorVintage.indicator == ind,
                    MacroIndicatorVintage.value.isnot(None),
                )
                .order_by(MacroIndicatorVintage.ingested_at.desc())
                .limit(1)
            ).scalar()
            if row:
                st = classify_staleness(row)
                if st.state == "fresh":
                    fresh += 1
                elif st.state == "yellow":
                    stale += 1
                else:
                    very_stale += 1
            else:
                very_stale += 1

    fresh_pct = round((fresh / total_ind * 100) if total_ind > 0 else 0, 1)

    # Portfolio risk ranking
    ranked = sorted(countries, key=lambda c: c.composite_risk_score or 0, reverse=True)
    ranking = []
    for i, c in enumerate(ranked[:10]):
        score = c.composite_risk_score or 0
        ranking.append(
            {
                "rank": i + 1,
                "iso": c.iso3,
                "name": c.name,
                "score": score,
                "label": _label(score),
                "status_tags": c.status_tags or [],
            }
        )

    # Recent rating actions
    ratings = list(
        session.execute(
            select(RatingHistory).order_by(RatingHistory.action_date.desc()).limit(10)
        ).scalars()
    )

    rating_actions = []
    for r in ratings:
        action_lower = (r.action or "").lower()
        action_type = (
            "downgrade"
            if "down" in action_lower or "default" in action_lower or "restrict" in action_lower
            else ("upgrade" if "up" in action_lower else "affirm")
        )
        rating_actions.append(
            {
                "date": r.action_date.isoformat() if r.action_date else None,
                "iso": r.iso3,
                "country_name": next((c.name for c in countries if c.iso3 == r.iso3), r.iso3),
                "agency": r.agency,
                "action": r.action,
                "rating": r.rating,
                "outlook": r.outlook,
                "action_type": action_type,
            }
        )

    return {
        "as_of": datetime.now(UTC).isoformat(),
        "countries_under_watch": {
            "elevated_count": len(elevated),
            "total_count": len(countries),
            "countries": [c.iso3 for c in elevated],
        },
        "portfolio_risk": {
            "average_score": avg_score,
            "count": len(scores),
            "history_delta_30d": None,
            "history_available": False,
        },
        "staleness_index": {
            "fresh_count": fresh,
            "stale_count": stale,
            "very_stale_count": very_stale,
            "total_count": total_ind,
            "fresh_pct": fresh_pct,
        },
        "active_alerts": {"status": "pending", "phase": "4c"},
        "portfolio_risk_ranking": ranking,
        "recent_rating_actions": rating_actions,
    }


@router.get("/intelligence-feed")
def intelligence_feed(
    session: DbSession,
    _: CurrentUser,
    limit: int = Query(5, ge=1, le=20),
    min_impact: int = Query(60, ge=0, le=100),
    since_days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    cutoff = datetime.now(UTC) - timedelta(days=since_days)

    rows = session.execute(
        select(NewsItem, NewsImpactScore)
        .join(NewsImpactScore, NewsItem.id == NewsImpactScore.news_item_id)
        .where(NewsItem.published_at >= cutoff, NewsItem.primary_iso3.isnot(None))
        .order_by(NewsItem.published_at.desc())
        .limit(100)
    ).all()

    def impact_to_num(level: str) -> int:
        return 80 if level == "H" else (50 if level == "M" else 20)

    articles = []
    for item, score in rows:
        impacts = {
            "fiscal": impact_to_num(score.fiscal_impact),
            "external": impact_to_num(score.external_impact),
            "fx": impact_to_num(score.fx_impact),
            "political": impact_to_num(score.political_impact),
        }
        overall = max(impacts.values())
        if overall < min_impact:
            continue

        highlights = []
        for axis, val in impacts.items():
            if val >= 40:
                highlights.append({"axis": axis, "level": "H" if val >= 70 else "M"})

        # Get country name
        country = session.get(Country, item.primary_iso3)
        country_name = country.name if country else item.primary_iso3

        articles.append(
            {
                "id": str(item.id),
                "headline": item.title,
                "source": item.source,
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "country_iso": item.primary_iso3,
                "country_name": country_name,
                "overall_impact": overall,
                "impact_scores": impacts,
                "tag_highlights": highlights,
            }
        )

        if len(articles) >= limit:
            break

    return {"articles": articles}
