import uuid
from datetime import UTC, datetime

import httpx
import pytest
from atlas_api.ingestion.imf import ImfWeoIngester
from atlas_api.models import Country, DataVintage

pytestmark = pytest.mark.asyncio


def _seed(session):
    session.add(Country(
        iso3="GHA", name="Ghana", capital="Accra", region="West Africa",
        tags=["SSA"], tier="C", status="restructured", fx_regime="float",
        fx_regime_notes=None, fx_parallel_premium=None,
    ))
    v = DataVintage(id=uuid.uuid4(), source="test", created_at=datetime.now(UTC))
    session.add(v)
    session.commit()
    return v.id


async def test_imf_writes_rows(httpx_mock, session):
    vintage_id = _seed(session)

    def _response(request: httpx.Request) -> httpx.Response:
        # Match indicator code out of URL path segment.
        parts = request.url.path.split("/")
        indicator = parts[-2]
        iso3 = parts[-1]
        return httpx.Response(200, json={
            "values": {indicator: {iso3: {"2023": 4.1, "2024": 3.8, "2025": 5.2}}}
        })

    httpx_mock.add_callback(_response, is_reusable=True)

    async with httpx.AsyncClient() as http:
        ing = ImfWeoIngester(http, session)
        from atlas_api.ingestion import imf as imf_mod
        original = imf_mod.COUNTRIES
        imf_mod.COUNTRIES = ("GHA",)
        try:
            stats = await ing.run(vintage_id)
        finally:
            imf_mod.COUNTRIES = original

    assert stats.rows_written > 0
    assert not stats.errors


async def test_imf_handles_missing_series(httpx_mock, session):
    vintage_id = _seed(session)
    httpx_mock.add_response(json={"values": {}}, is_reusable=True)

    async with httpx.AsyncClient() as http:
        ing = ImfWeoIngester(http, session)
        from atlas_api.ingestion import imf as imf_mod
        original = imf_mod.COUNTRIES
        imf_mod.COUNTRIES = ("GHA",)
        try:
            stats = await ing.run(vintage_id)
        finally:
            imf_mod.COUNTRIES = original

    assert stats.rows_written == 0
    assert not stats.errors  # missing series is not an error, just empty
