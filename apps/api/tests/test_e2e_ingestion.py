"""Full orchestrator run against mocked external APIs; verifies vintage rows + read paths."""

import httpx
import pytest
from atlas_api.ingestion.orchestrator import run_nightly
from atlas_api.models import (
    Country,
    DataVintage,
    FxRate,
    IngestionCircuit,
    MacroIndicatorVintage,
    RatingHistory,
)
from atlas_api.services.country.queries import get_latest, get_latest_fx, get_rating_history
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.asyncio


COUNTRIES = ("CIV", "GHA", "KEN", "NGA", "SEN", "ETH", "RWA", "ZAF", "MAR", "EGY")


def _seed_countries(session):
    for iso3 in COUNTRIES:
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
    session.commit()


async def test_e2e_with_mocked_externals(httpx_mock, engine, monkeypatch):
    # Rebind SessionLocal to test engine so the orchestrator's own SessionLocal uses tests' DB.
    # Per Task 15 lesson: must patch BOTH db_mod.SessionLocal AND orchestrator.SessionLocal
    # because orchestrator uses `from atlas_api.db import SessionLocal` (binds at import time).
    from atlas_api import db as db_mod
    from atlas_api.ingestion import orchestrator as orch_mod

    test_session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )
    monkeypatch.setattr(db_mod, "SessionLocal", test_session_factory)
    monkeypatch.setattr(orch_mod, "SessionLocal", test_session_factory)

    # Because the orchestrator commits with its own SessionLocal (bypassing the
    # savepoint-wrapped `session` fixture), bleed-through from prior runs and
    # the current test must be cleared at the DB level. Do this up front.
    with test_session_factory() as cleanup_session:
        cleanup_session.execute(delete(MacroIndicatorVintage))
        cleanup_session.execute(delete(FxRate))
        cleanup_session.execute(delete(RatingHistory))
        cleanup_session.execute(delete(DataVintage))
        cleanup_session.execute(delete(IngestionCircuit))
        cleanup_session.execute(delete(Country))
        cleanup_session.commit()

    # Seed countries through a committed session so the orchestrator's fresh
    # session can see them (FK targets for macro_indicator_vintage.iso3 etc.).
    with test_session_factory() as seed_session:
        _seed_countries(seed_session)

    # Stub all external HTTP: WB + IMF return a tiny series, FX returns a rate map.
    def _response(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if "worldbank.org" in host:
            return httpx.Response(
                200,
                json=[
                    {"page": 1, "pages": 1, "total": 1},
                    [
                        {
                            "date": "2024",
                            "value": 10.0,
                            "indicator": {"id": "X", "value": "X"},
                            "country": {"id": "X", "value": "X"},
                            "countryiso3code": "XXX",
                            "unit": "",
                            "obs_status": "",
                            "decimal": 1,
                        }
                    ],
                ],
            )
        if "imf.org" in host:
            parts = request.url.path.split("/")
            indicator, iso3 = parts[-2], parts[-1]
            return httpx.Response(
                200, json={"values": {indicator: {iso3: {"2024": 5.5}}}}
            )
        if "open.er-api.com" in host:
            return httpx.Response(
                200,
                json={
                    "result": "success",
                    "base_code": "USD",
                    "time_last_update_unix": 1744761600,
                    "rates": {
                        "XOF": 600,
                        "GHS": 15.2,
                        "KES": 129.4,
                        "NGN": 1450,
                        "ETB": 56.8,
                        "RWF": 1350,
                        "ZAR": 18.4,
                        "MAD": 10.1,
                        "EGP": 48.5,
                    },
                },
            )
        return httpx.Response(404)

    httpx_mock.add_callback(_response, is_reusable=True)

    report = await run_nightly()

    assert report.ok is True
    # Verify via a fresh committed session (orchestrator commits bypass the
    # savepoint-wrapped `session` fixture, so we cannot reuse it here).
    with test_session_factory() as read_session:
        macro_rows = read_session.execute(select(MacroIndicatorVintage)).scalars().all()
        assert len(macro_rows) > 0
        fx_rows = read_session.execute(select(FxRate)).scalars().all()
        assert len(fx_rows) == 10
        rating_rows = read_session.execute(select(RatingHistory)).scalars().all()
        assert len(rating_rows) > 0

        # Exercise read paths on a real ingested country.
        assert (
            get_latest(read_session, "GHA", "GDP_USD") is not None
            or get_latest(read_session, "GHA", "INFLATION_PCT") is not None
        )
        assert get_latest_fx(read_session, "GHA") is not None
        assert len(get_rating_history(read_session, "GHA")) > 0

    # Clean up the committed rows this test wrote, so the rest of the suite
    # (which relies on rollback-based isolation) sees an empty DB.
    with test_session_factory() as cleanup_session:
        cleanup_session.execute(delete(MacroIndicatorVintage))
        cleanup_session.execute(delete(FxRate))
        cleanup_session.execute(delete(RatingHistory))
        cleanup_session.execute(delete(DataVintage))
        cleanup_session.execute(delete(IngestionCircuit))
        cleanup_session.execute(delete(Country))
        cleanup_session.commit()
