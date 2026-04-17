import uuid
from datetime import UTC, date, datetime

from atlas_api.models import (
    Country,
    DataVintage,
    MacroIndicatorVintage,
    RatingHistory,
    User,
)
from atlas_api.security import hash_password


def _seed_user(session):
    session.add(User(
        id=uuid.uuid4(), email="a@b.test",
        password_hash=hash_password("pw-123456"), role="Analyst",
    ))
    session.commit()


def _seed_gha_with_data(session):
    session.add(Country(
        iso3="GHA", name="Ghana", capital="Accra", region="West Africa",
        tags=["SSA"], tier="C", status="restructured", fx_regime="float",
        fx_regime_notes=None, fx_parallel_premium=None,
    ))
    v = DataVintage(id=uuid.uuid4(), source="test", created_at=datetime.now(UTC))
    session.add(v)
    session.add(MacroIndicatorVintage(
        id=uuid.uuid4(), iso3="GHA", indicator="PUBLIC_DEBT_PCT_GDP",
        period="2024", value=83.0, source="worldbank",
        source_date=date(2024, 12, 31), vintage_id=v.id,
    ))
    session.add(RatingHistory(
        id=uuid.uuid4(), iso3="GHA", agency="S&P", rating="CCC+",
        outlook="stable", action="upgrade", action_date=date(2024, 5, 1),
    ))
    session.commit()


def _login(client):
    r = client.post("/api/auth/login", json={"email": "a@b.test", "password": "pw-123456"})
    assert r.status_code == 200


def test_bundle_requires_auth(client):
    r = client.get("/api/countries/GHA/bundle")
    assert r.status_code == 401


def test_bundle_returns_full_shape(client, session):
    _seed_user(session)
    _seed_gha_with_data(session)
    _login(client)
    r = client.get("/api/countries/GHA/bundle")
    assert r.status_code == 200
    body = r.json()
    assert body["country"]["iso3"] == "GHA"
    assert body["country"]["status"] == "restructured"
    assert len(body["macro"]) == 12
    debt = next(t for t in body["macro"] if t["indicator"] == "PUBLIC_DEBT_PCT_GDP")
    assert debt["value"] == 83.0
    assert debt["staleness"]["state"] == "fresh"
    assert "S&P" in body["ratings"]["latest_per_agency"]
    assert body["ratings"]["composite_score"] is not None
    assert body["risk"]["composite"] >= 0
    assert len(body["risk"]["dimensions"]) == 6
    assert body["synopsis"] is None
    assert body["news_placeholder"] is True


def test_bundle_404(client, session):
    _seed_user(session)
    _login(client)
    r = client.get("/api/countries/ZZZ/bundle")
    assert r.status_code == 404


def test_bundle_iso3_case_normalized(client, session):
    _seed_user(session)
    _seed_gha_with_data(session)
    _login(client)
    r = client.get("/api/countries/gha/bundle")
    assert r.status_code == 200
    assert r.json()["country"]["iso3"] == "GHA"
