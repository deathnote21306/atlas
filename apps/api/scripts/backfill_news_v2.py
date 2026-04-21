"""Backfill news: fetch English + non-English articles, translate non-English titles, NER + score."""  # noqa: E501

import asyncio
import re
import sys

import httpx

sys.path.insert(0, "packages/schemas/src")
sys.path.insert(0, "apps/api/src")


def is_mostly_latin(text: str) -> bool:
    if not text:
        return False
    latin = sum(1 for c in text if c.isascii() or ord(c) < 0x250)
    return latin / len(text) > 0.6


async def translate_titles(titles: list[str]) -> list[str]:
    """Translate non-English titles using Claude."""
    try:
        import anthropic
        from atlas_api.config import settings

        if not settings.anthropic_api_key:
            print("No Anthropic API key — skipping translation")
            return titles

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        # Batch all titles in one call for efficiency
        numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles))
        prompt = f"""Translate each headline to English. Keep numbered format.

{numbered}"""

        response = client.messages.create(
            model="claude-sonnet-4-5-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]

        translated = []
        for line in lines:
            # Strip leading number + dot/parenthesis
            cleaned = re.sub(r"^\d+[\.\)]\s*", "", line)
            translated.append(cleaned)

        tokens = response.usage.input_tokens + response.usage.output_tokens
        print(f"Translated {len(translated)} titles using {tokens} tokens")

        # Pad if we got fewer translations than expected
        while len(translated) < len(titles):
            translated.append(titles[len(translated)])

        return translated[: len(titles)]
    except Exception as e:
        print(f"Translation failed: {e} — keeping original titles")
        return titles


async def main() -> None:
    from atlas_api.db import SessionLocal
    from atlas_api.models import NewsImpactScore, NewsItem
    from atlas_api.services.news.dedup import store_new_articles
    from atlas_api.services.news.gdelt import poll_gdelt
    from atlas_api.services.news.heuristic_scorer import persist_score, score_impact
    from atlas_api.services.news.nlp import classify_event, extract_country
    from atlas_api.services.news.rss import poll_rss
    from sqlalchemy import func, select

    session = SessionLocal()

    try:
        async with httpx.AsyncClient() as http:
            # Pass 1: English-only articles (fills coverage gaps)
            print("=== Pass 1: English-only GDELT + RSS ===")
            eng_articles = await poll_gdelt(http, english_only=True, max_records=30)
            rss_articles = await poll_rss(http)
            all_eng = eng_articles + rss_articles
            print(f"Polled {len(all_eng)} English articles")

            new_eng = store_new_articles(session, all_eng)
            print(f"Stored {len(new_eng)} new English articles")

            # Pass 2: All-language articles
            print("\n=== Pass 2: All-language GDELT ===")
            all_articles = await poll_gdelt(http, english_only=False, max_records=30)
            new_all = store_new_articles(session, all_articles)
            print(f"Stored {len(new_all)} new all-language articles")

        # Identify non-English articles for translation
        all_new = new_eng + new_all
        non_english = [item for item in all_new if not is_mostly_latin(item.title)]
        print(f"\nNon-English articles to translate: {len(non_english)}")

        if non_english:
            original_titles = [item.title for item in non_english]
            translated = await translate_titles(original_titles)
            for item, new_title in zip(non_english, translated, strict=False):
                if new_title != item.title:
                    item.title = new_title
            session.commit()

        # NER + event classification + scoring for ALL new articles
        print("\n=== Processing all new articles ===")
        ner_count = 0
        event_count = 0
        scored_count = 0

        keywords = {
            "KEN": ["kenya", "kenyan", "nairobi", "shilling", "kenyatta"],
            "CIV": ["ivory coast", "ivoire", "abidjan", "ivorian", "ouattara"],
            "SEN": ["senegal", "senegalese", "dakar"],
            "ZAF": [
                "south africa",
                "south african",
                "pretoria",
                "johannesburg",
                "rand",
                "ramaphosa",
            ],
            "MAR": ["morocco", "moroccan", "rabat", "casablanca", "dirham"],
            "EGY": ["egypt", "egyptian", "cairo", "suez", "sisi"],
            "ETH": ["ethiopia", "ethiopian", "addis", "abiy"],
            "GHA": ["ghana", "ghanaian", "accra", "cedi"],
            "NGA": ["nigeria", "nigerian", "abuja", "lagos", "naira", "tinubu"],
            "RWA": ["rwanda", "rwandan", "kigali", "kagame"],
        }

        for item in all_new:
            # NER: try spaCy first, then keyword fallback
            if not item.primary_iso3:
                try:
                    iso3 = extract_country(item.title, item.body_text or "")
                except Exception:
                    iso3 = None

                if not iso3:
                    text_lower = (item.title + " " + (item.body_text or "")).lower()
                    for code, kws in keywords.items():
                        if any(kw in text_lower for kw in kws):
                            iso3 = code
                            break

                if iso3:
                    item.primary_iso3 = iso3
                    ner_count += 1

            # Event classification
            if not item.event_type:
                try:
                    event_type = classify_event(item.title, item.body_text or "")
                    if event_type:
                        item.event_type = event_type
                        event_count += 1
                except Exception:
                    pass

            # Heuristic scoring
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
                scored_count += 1

        session.commit()

        print(f"\nNER assigned: {ner_count}")
        print(f"Events classified: {event_count}")
        print(f"Heuristic scored: {scored_count}")

        # Final counts
        rows = session.execute(
            select(NewsItem.primary_iso3, func.count())
            .where(NewsItem.primary_iso3.isnot(None))
            .group_by(NewsItem.primary_iso3)
            .order_by(func.count().desc())
        ).all()
        print("\n=== Final article counts ===")
        for iso, cnt in rows:
            print(f"  {iso}: {cnt}")

        unassigned = session.execute(
            select(func.count()).where(NewsItem.primary_iso3.is_(None))
        ).scalar()
        print(f"  (unassigned): {unassigned}")

    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
