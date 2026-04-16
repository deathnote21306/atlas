import uuid
from datetime import UTC, date, datetime

import httpx
import pytest
from atlas_api.ingestion.fx import ExchangeRateHostIngester
from atlas_api.models import Country, DataVintage, FxRate
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


def _seed_countries(session):
    for iso3, name in [
        ("CIV", "Côte d'Ivoire"), ("GHA", "Ghana"), ("KEN", "Kenya"),
        ("NGA", "Nigeria"), ("SEN", "Senegal"), ("ETH", "Ethiopia"),
        ("RWA", "Rwanda"), ("ZAF", "South Africa"), ("MAR", "Morocco"), ("EGY", "Egypt"),
    ]:
        session.add(Country(
            iso3=iso3, name=name, capital="?", region="?",
            tags=[], tier="B", status="performing", fx_regime="float",
            fx_regime_notes=None, fx_parallel_premium=None,
        ))
    v = DataVintage(id=uuid.uuid4(), source="test", created_at=datetime.now(UTC))
    session.add(v)
    session.commit()
    return v.id


async def test_fx_writes_daily_rows(httpx_mock, session):
    vintage_id = _seed_countries(session)
    httpx_mock.add_response(
        url=httpx.URL(
            "https://api.exchangerate.host/latest",
            params={"base": "USD", "symbols": "EGP,ETB,GHS,KES,MAD,NGN,RWF,XOF,ZAR"},
        ),
        json={
            "base": "USD",
            "date": "2026-04-16",
            "rates": {
                "XOF": 600.0, "GHS": 15.2, "KES": 129.4, "NGN": 1450.0,
                "ETB": 56.8, "RWF": 1350.0, "ZAR": 18.4, "MAD": 10.1, "EGP": 48.5,
            },
        },
    )

    async with httpx.AsyncClient() as http:
        ing = ExchangeRateHostIngester(http, session)
        stats = await ing.run(vintage_id)

    assert stats.rows_written == 10  # CIV + SEN both use XOF
    assert not stats.errors
    rows = session.execute(select(FxRate)).scalars().all()
    assert len(rows) == 10
    assert all(r.observation_date == date(2026, 4, 16) for r in rows)


async def test_fx_handles_missing_currency(httpx_mock, session):
    vintage_id = _seed_countries(session)
    httpx_mock.add_response(json={
        "base": "USD", "date": "2026-04-16",
        "rates": {"GHS": 15.2},  # only one currency returned
    })
    async with httpx.AsyncClient() as http:
        ing = ExchangeRateHostIngester(http, session)
        stats = await ing.run(vintage_id)
    assert stats.rows_written == 1
    assert stats.rows_skipped == 9
