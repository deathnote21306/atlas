"""Fix 1: Re-score articles with Claude (batch 1 of 5, ~40k token budget).
Fix 2: Backfill CIV articles with fixed GDELT query.
"""

import asyncio
import sys

import httpx

sys.path.insert(0, "packages/schemas/src")
sys.path.insert(0, "apps/api/src")


def is_mostly_latin(text: str) -> bool:
    if not text:
        return False
    latin = sum(1 for c in text if c.isascii() or ord(c) < 0x250)
    return latin / len(text) > 0.6


KEYWORDS = {
    "KEN": ["kenya", "kenyan", "nairobi", "shilling"],
    "CIV": ["ivory coast", "ivoire", "abidjan", "ivorian", "cocoa"],
    "SEN": ["senegal", "senegalese", "dakar"],
    "ZAF": ["south africa", "south african", "pretoria", "johannesburg"],
    "MAR": ["morocco", "moroccan", "rabat", "casablanca"],
    "EGY": ["egypt", "egyptian", "cairo", "suez"],
    "ETH": ["ethiopia", "ethiopian", "addis"],
    "GHA": ["ghana", "ghanaian", "accra", "cedi"],
    "NGA": ["nigeria", "nigerian", "abuja", "lagos", "naira"],
    "RWA": ["rwanda", "rwandan", "kigali"],
}


async def backfill_civ() -> int:
    """Fetch CIV articles with fixed query."""
    from atlas_api.db import SessionLocal
    from atlas_api.models import NewsImpactScore
    from atlas_api.services.news.dedup import store_new_articles
    from atlas_api.services.news.gdelt import poll_gdelt
    from atlas_api.services.news.heuristic_scorer import persist_score, score_impact
    from atlas_api.services.news.nlp import classify_event
    from sqlalchemy import select

    print("=== Backfilling CIV ===")
    session = SessionLocal()
    try:
        async with httpx.AsyncClient() as http:
            articles = await poll_gdelt(http, english_only=True, max_records=40)

        # Filter to CIV-related only
        civ_articles = [
            a
            for a in articles
            if any(kw in (a.title + " " + (a.body_snippet or "")).lower() for kw in KEYWORDS["CIV"])
        ]
        print(f"CIV-relevant from GDELT: {len(civ_articles)}")

        new_items = store_new_articles(session, civ_articles)
        print(f"New CIV articles stored: {len(new_items)}")

        for item in new_items:
            if not item.primary_iso3:
                item.primary_iso3 = "CIV"
            event_type = classify_event(item.title, item.body_text or "")
            if event_type:
                item.event_type = event_type

            existing = (
                session.execute(
                    select(NewsImpactScore).where(NewsImpactScore.news_item_id == item.id)
                )
                .scalars()
                .first()
            )
            if not existing:
                scores = score_impact(item.title, item.body_text or "")
                persist_score(session, item.id, scores)

        session.commit()
        return len(new_items)
    finally:
        session.close()


def rescore_batch(max_tokens: int = 40000) -> dict[str, int]:
    """Re-score heuristic articles with Claude, respecting token budget."""
    from atlas_api.db import SessionLocal
    from atlas_api.models import NewsImpactScore, NewsItem
    from atlas_api.services.ai.news_scorer import score_with_ai
    from sqlalchemy import delete, select

    stats = {"claude_scored": 0, "claude_failed": 0, "skipped_budget": 0, "total_tokens": 0}

    session = SessionLocal()
    try:
        # Get all heuristic-scored articles, prioritize by impact (H axes count)
        scored_items = session.execute(
            select(NewsImpactScore, NewsItem)
            .join(NewsItem, NewsImpactScore.news_item_id == NewsItem.id)
            .where(NewsImpactScore.scorer == "heuristic")
            .order_by(NewsItem.published_at.desc())
        ).all()

        print(f"\nHeuristic-scored articles to re-score: {len(scored_items)}")
        print(f"Token budget for this run: {max_tokens}")

        for score_row, item in scored_items:
            remaining = max_tokens - stats["total_tokens"]
            if remaining < 2500:
                stats["skipped_budget"] = (
                    len(scored_items) - stats["claude_scored"] - stats["claude_failed"]
                )
                print(f"Token budget exhausted after {stats['claude_scored']} articles")
                break

            # Delete existing heuristic score
            session.execute(delete(NewsImpactScore).where(NewsImpactScore.id == score_row.id))
            session.flush()

            ai_score = score_with_ai(
                session,
                news_item_id=item.id,
                title=item.title,
                body=item.body_text or "",
                iso3=item.primary_iso3,
                event_type=item.event_type,
            )

            if ai_score is not None:
                stats["claude_scored"] += 1
                stats["total_tokens"] += 2000  # approximate
                if stats["claude_scored"] % 10 == 0:
                    print(f"  ...scored {stats['claude_scored']} articles")
            else:
                # Claude failed — re-create heuristic score
                from atlas_api.services.news.heuristic_scorer import persist_score, score_impact

                scores = score_impact(item.title, item.body_text or "")
                persist_score(session, item.id, scores)
                stats["claude_failed"] += 1

            session.commit()

        print(f"\nRe-scoring complete: {stats}")
        return stats
    finally:
        session.close()


async def main() -> None:
    # Fix 2: Backfill CIV
    await backfill_civ()

    # Fix 1: Re-score batch 1 (~40k tokens, ~16-20 articles)
    rescore_batch(max_tokens=40000)

    # Final audit
    from atlas_api.db import SessionLocal
    from atlas_api.models import NewsImpactScore, NewsItem
    from sqlalchemy import func, select

    with SessionLocal() as s:
        print("\n=== FINAL COVERAGE ===")
        rows = s.execute(
            select(NewsItem.primary_iso3, func.count())
            .where(NewsItem.primary_iso3.isnot(None))
            .group_by(NewsItem.primary_iso3)
            .order_by(func.count().desc())
        ).all()
        for iso, cnt in rows:
            print(f"  {iso}: {cnt}")

        claude_count = s.execute(
            select(func.count()).where(NewsImpactScore.scorer != "heuristic")
        ).scalar()
        heuristic_count = s.execute(
            select(func.count()).where(NewsImpactScore.scorer == "heuristic")
        ).scalar()
        print(f"\nScoring: {claude_count} Claude, {heuristic_count} heuristic")


if __name__ == "__main__":
    asyncio.run(main())
