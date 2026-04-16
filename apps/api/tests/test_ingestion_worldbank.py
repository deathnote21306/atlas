import uuid
from datetime import UTC, datetime

import httpx
import pytest
from atlas_api.ingestion.worldbank import WorldBankIngester
from atlas_api.models import Country, DataVintage, MacroIndicatorVintage
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


def _seed_one_country(session):
    session.add(Country(
        iso3="GHA", name="Ghana", capital="Accra", region="West Africa",
        tags=["SSA"], tier="C", status="restructured", fx_regime="float",
        fx_regime_notes=None, fx_parallel_premium=None,
    ))
    v = DataVintage(id=uuid.uuid4(), source="test", created_at=datetime.now(UTC))
    session.add(v)
    session.commit()
    return v.id


async def test_worldbank_writes_rows(httpx_mock, session):
    vintage_id = _seed_one_country(session)

    # Match all WB URLs for GHA; return a canned 2024 + 2023 payload.
    def _response(request: httpx.Request) -> httpx.Response:
        ind = {"id": "X", "value": "X"}
        ctry = {"id": "GH", "value": "Ghana"}
        return httpx.Response(200, json=[
            {"page": 1, "pages": 1, "total": 2},
            [
                {
                    "indicator": ind, "country": ctry, "countryiso3code": "GHA",
                    "date": "2024", "value": 22.4, "unit": "",
                    "obs_status": "", "decimal": 1,
                },
                {
                    "indicator": ind, "country": ctry, "countryiso3code": "GHA",
                    "date": "2023", "value": 31.5, "unit": "",
                    "obs_status": "", "decimal": 1,
                },
            ],
        ])

    httpx_mock.add_callback(_response, is_reusable=True)

    async with httpx.AsyncClient() as http:
        ing = WorldBankIngester(http, session)
        # Trim to just GHA for this test.
        from atlas_api.ingestion import worldbank
        original_countries = worldbank.COUNTRIES
        worldbank.COUNTRIES = ("GHA",)
        try:
            stats = await ing.run(vintage_id)
        finally:
            worldbank.COUNTRIES = original_countries

    assert stats.rows_written > 0
    assert not stats.errors

    # Confirm at least one row persisted and links to our vintage.
    rows = session.execute(
        select(MacroIndicatorVintage).where(MacroIndicatorVintage.vintage_id == vintage_id)
    ).scalars().all()
    assert len(rows) >= 2


async def test_worldbank_records_errors_on_5xx(httpx_mock, session):
    vintage_id = _seed_one_country(session)
    httpx_mock.add_response(status_code=500, is_reusable=True)

    async with httpx.AsyncClient() as http:
        ing = WorldBankIngester(http, session)
        from atlas_api.ingestion import worldbank
        original = worldbank.COUNTRIES
        worldbank.COUNTRIES = ("GHA",)
        try:
            stats = await ing.run(vintage_id)
        finally:
            worldbank.COUNTRIES = original

    assert stats.rows_written == 0
    assert len(stats.errors) > 0
