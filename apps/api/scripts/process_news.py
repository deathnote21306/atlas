"""Process unscored news items: NER country extraction + event classification + heuristic scoring."""  # noqa: E501

from atlas_api.db import SessionLocal
from atlas_api.models import NewsImpactScore, NewsItem
from atlas_api.services.news.heuristic_scorer import persist_score, score_impact
from atlas_api.services.news.nlp import classify_event, extract_country
from sqlalchemy import select


def main() -> None:
    with SessionLocal() as s:
        items = s.execute(select(NewsItem).order_by(NewsItem.published_at.desc())).scalars().all()

        ner_assigned = 0
        events_classified = 0
        scored = 0

        for item in items:
            # NER country extraction
            if not item.primary_iso3:
                iso3 = extract_country(item.title, item.body_text or "")
                if iso3:
                    item.primary_iso3 = iso3
                    ner_assigned += 1

            # Event classification
            if not item.event_type:
                event_type = classify_event(item.title, item.body_text or "")
                if event_type:
                    item.event_type = event_type
                    events_classified += 1

            # Heuristic scoring (skip if already scored)
            existing = (
                s.execute(select(NewsImpactScore).where(NewsImpactScore.news_item_id == item.id))
                .scalars()
                .first()
            )
            if not existing:
                scores = score_impact(item.title, item.body_text or "")
                persist_score(s, item.id, scores)
                scored += 1

        s.commit()

        # Summary
        print(f"NER assigned: {ner_assigned}")
        print(f"Events classified: {events_classified}")
        print(f"Heuristic scored: {scored}")

        # Per-country counts
        from sqlalchemy import func

        rows = s.execute(
            select(NewsItem.primary_iso3, func.count())
            .group_by(NewsItem.primary_iso3)
            .order_by(func.count().desc())
        ).all()
        print("\nArticles per country:")
        for iso, cnt in rows:
            print(f"  {iso or '(unassigned)'}: {cnt}")


if __name__ == "__main__":
    main()
