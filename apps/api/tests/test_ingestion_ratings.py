import uuid
from datetime import UTC, datetime

import httpx
import pytest
from atlas_api.ingestion.ratings import RatingsJsonLoader
from atlas_api.models import Country, DataVintage

pytestmark = pytest.mark.asyncio


def _seed(session):
    for iso3 in ("CIV", "GHA", "KEN", "NGA", "SEN", "ETH", "RWA", "ZAF", "MAR", "EGY"):
        session.add(
            Country(
                iso3=iso3,
                name=iso3,
                capital="?",
                region="?",
                tags=[],
                tier="B",
                status="performing",
                fx_regime="float",
                fx_regime_notes=None,
                fx_parallel_premium=None,
            )
        )
    v = DataVintage(id=uuid.uuid4(), source="test", created_at=datetime.now(UTC))
    session.add(v)
    session.commit()
    return v.id


async def test_ratings_first_run_inserts_all(session):
    vintage_id = _seed(session)
    async with httpx.AsyncClient() as http:
        loader = RatingsJsonLoader(http, session)
        stats = await loader.run(vintage_id)
    assert stats.rows_written >= 20
    assert stats.rows_skipped == 0


async def test_ratings_second_run_skips_all(session):
    vintage_id = _seed(session)
    async with httpx.AsyncClient() as http:
        loader = RatingsJsonLoader(http, session)
        first = await loader.run(vintage_id)
        second = await loader.run(vintage_id)
    assert first.rows_written >= 20
    assert second.rows_written == 0
    assert second.rows_skipped == first.rows_written
