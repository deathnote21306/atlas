"""Ratings JSON loader — diffs against rating_history, inserts only new actions."""

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import structlog
from sqlalchemy import select

from atlas_api.ingestion.base import Ingester, SourceStats
from atlas_api.models import RatingHistory

log = structlog.get_logger()

SEED_PATH = Path(__file__).resolve().parents[5] / "infra" / "seed" / "ratings.json"


class RatingsJsonLoader(Ingester):
    source_name = "ratings_json"

    async def run(self, vintage_id: UUID) -> SourceStats:
        stats = SourceStats(source=self.source_name)
        try:
            records = json.loads(SEED_PATH.read_text())
        except FileNotFoundError as exc:
            stats.errors.append(f"seed not found: {exc}")
            return stats

        for r in records:
            iso3 = r["iso3"]
            agency = r["agency"]
            rating = r["rating"]
            action_date = date.fromisoformat(r["action_date"])
            # Dedupe on (iso3, agency, rating, action_date): idempotent loads.
            existing = self.session.execute(
                select(RatingHistory.id).where(
                    RatingHistory.iso3 == iso3,
                    RatingHistory.agency == agency,
                    RatingHistory.rating == rating,
                    RatingHistory.action_date == action_date,
                )
            ).scalar_one_or_none()
            if existing is not None:
                stats.rows_skipped += 1
                continue
            self.session.add(
                RatingHistory(
                    id=uuid.uuid4(),
                    iso3=iso3,
                    agency=agency,
                    rating=rating,
                    outlook=r.get("outlook"),
                    action=r.get("action", "affirm"),
                    action_date=action_date,
                    source_url=r.get("source_url"),
                    ingested_at=datetime.now(UTC),
                )
            )
            stats.rows_written += 1
        self.session.commit()
        return stats
