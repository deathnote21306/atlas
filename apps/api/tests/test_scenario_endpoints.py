"""Integration tests for scenario endpoints.

Seeds a country + macro data, then exercises preview / save / get / list.
"""

import uuid

import pytest
from atlas_api.models import Country, DataVintage, MacroIndicatorVintage, User
from atlas_api.security import hash_password


@pytest.fixture()
def seeded(session):
    """Seed a country, user, vintage, and macro data for scenario tests."""
    user = User(
        id=uuid.uuid4(),
        email="analyst@atlas.test",
        password_hash=hash_password("pass1234"),
        role="Analyst",
    )
    session.add(user)

    country = Country(
        iso3="TST",
        name="Testland",
        capital="Testville",
        region="Test Region",
        tags=["test"],
        tier="1",
        status="performing",
        fx_regime="float",
    )
    session.add(country)

    vintage = DataVintage(source="test", notes="test vintage")
    session.add(vintage)
    session.flush()

    indicators = {
        "PUBLIC_DEBT_PCT_GDP": 60.0,
        "FISCAL_BALANCE_PCT_GDP": -3.0,
        "CURRENT_ACCOUNT_PCT_GDP": -2.0,
        "GDP_GROWTH_PCT": 4.0,
        "INFLATION_PCT": 8.0,
        "FX_RESERVES_MO_IMPORTS": 4.0,
    }
    for ind, val in indicators.items():
        session.add(MacroIndicatorVintage(
            iso3="TST",
            indicator=ind,
            value=val,
            source="test",
            period="2025",
            vintage_id=vintage.id,
        ))

    session.commit()
    return {"user": user, "vintage": vintage}


@pytest.fixture()
def auth_client(client, seeded):
    """Client with an active session cookie."""
    resp = client.post("/api/auth/login", json={
        "email": "analyst@atlas.test",
        "password": "pass1234",
    })
    assert resp.status_code == 200, resp.text
    return client


def test_preview_returns_shocked_values(auth_client):
    resp = auth_client.post("/api/scenarios/preview", json={
        "iso3": "TST",
        "shocks": {
            "gdp_shock": -2.0,
            "inflation_shock": 5.0,
            "fx_depreciation": 15.0,
            "rate_shock": 3.0,
            "commodity_shock": -10.0,
        },
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "new_risk_score" in data
    assert "distress_probability" in data
    assert "deltas" in data
    assert data["distress_probability"] is not None  # performing country
    assert data["deltas"]["fiscal_balance"] < 0  # negative shock


def test_preview_unknown_country_404(auth_client):
    resp = auth_client.post("/api/scenarios/preview", json={
        "iso3": "ZZZ",
        "shocks": {"gdp_shock": -1.0},
    })
    assert resp.status_code == 404


def test_save_then_get(auth_client):
    # Save
    resp = auth_client.post("/api/scenarios", json={
        "iso3": "TST",
        "shocks": {"gdp_shock": -2.0, "inflation_shock": 3.0},
    })
    assert resp.status_code == 201, resp.text
    saved = resp.json()
    assert "id" in saved
    scenario_id = saved["id"]

    # Get
    resp2 = auth_client.get(f"/api/scenarios/{scenario_id}")
    assert resp2.status_code == 200
    fetched = resp2.json()
    assert fetched["id"] == scenario_id
    assert fetched["iso3"] == "TST"
    assert fetched["shocks"]["gdp_shock"] == -2.0


def test_list_by_iso3(auth_client):
    # Save two scenarios
    auth_client.post("/api/scenarios", json={
        "iso3": "TST", "shocks": {"gdp_shock": -1.0},
    })
    auth_client.post("/api/scenarios", json={
        "iso3": "TST", "shocks": {"gdp_shock": -3.0},
    })

    resp = auth_client.get("/api/scenarios?iso3=TST")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 2
    # Newest first
    assert items[0]["shocks"]["gdp_shock"] == -3.0


def test_get_nonexistent_404(auth_client):
    resp = auth_client.get(f"/api/scenarios/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_preview_requires_auth(client):
    resp = client.post("/api/scenarios/preview", json={
        "iso3": "TST", "shocks": {"gdp_shock": -1.0},
    })
    assert resp.status_code == 401
