"""Tests for strict ISO3 validation on all endpoints."""

import uuid
from datetime import UTC, datetime

from atlas_api.models import Country, User
from atlas_api.security import hash_password
from atlas_api.services.news.dedup import url_hash
from atlas_api.models import NewsItem


def _seed_user(session):
    session.add(User(
        id=uuid.uuid4(), email="iso3test@b.test",
        password_hash=hash_password("pw-123456"), role="Analyst",
    ))
    session.commit()


def _login(client):
    r = client.post("/api/auth/login", json={"email": "iso3test@b.test", "password": "pw-123456"})
    assert r.status_code == 200


def _seed_country(session, iso3="NGA"):
    session.add(Country(
        iso3=iso3, name="Nigeria", capital="Abuja", region="West Africa",
        tags=["SSA"], tier="B", status="performing", fx_regime="float",
        fx_regime_notes=None, fx_parallel_premium=None,
    ))
    session.commit()


def _seed_news(session, iso3="NGA"):
    item = NewsItem(
        id=uuid.uuid4(), url="https://test.com/iso3test",
        url_hash=url_hash("https://test.com/iso3test"),
        title="Nigeria test article", source="reuters",
        published_at=datetime.now(UTC), body_text="Test body...",
        primary_iso3=iso3, event_type="Fiscal", ingested_at=datetime.now(UTC),
    )
    session.add(item)
    session.commit()
    return item


# --- News endpoint tests ---

def test_news_iso3_invalid_returns_400(session, client):
    _seed_user(session)
    _login(client)
    r = client.get("/api/news?iso3=INVALID")
    assert r.status_code == 400
    assert "Invalid ISO3 code" in r.json()["detail"]


def test_news_iso3_numeric_returns_400(session, client):
    _seed_user(session)
    _login(client)
    r = client.get("/api/news?iso3=123")
    assert r.status_code == 400
    assert "Invalid ISO3 code" in r.json()["detail"]


def test_news_iso3_lowercase_accepted(session, client):
    _seed_user(session)
    _seed_country(session, "NGA")
    _seed_news(session, "NGA")
    _login(client)
    r = client.get("/api/news?iso3=nga")
    assert r.status_code == 200


def test_news_iso3_special_chars_returns_400(session, client):
    _seed_user(session)
    _login(client)
    r = client.get("/api/news?iso3=NG!")
    assert r.status_code == 400


# --- Countries path-param endpoint tests ---

def test_countries_iso3_invalid_returns_400(session, client):
    _seed_user(session)
    _login(client)
    r = client.get("/api/countries/TOOLONG")
    assert r.status_code == 400
    assert "Invalid ISO3 code" in r.json()["detail"]


def test_countries_iso3_numeric_returns_400(session, client):
    _seed_user(session)
    _login(client)
    r = client.get("/api/countries/123")
    assert r.status_code == 400


def test_countries_iso3_lowercase_accepted(session, client):
    _seed_user(session)
    _seed_country(session, "NGA")
    _login(client)
    r = client.get("/api/countries/nga")
    # Should not be 400; could be 200 if found or 404 if not
    assert r.status_code in (200, 404)


# --- Synopses path-param endpoint test ---

def test_synopses_iso3_invalid_returns_400(session, client):
    r = client.get("/api/synopses/12X4")
    assert r.status_code == 400
    assert "Invalid ISO3 code" in r.json()["detail"]


def test_synopses_iso3_lowercase_accepted(session, client):
    r = client.get("/api/synopses/nga")
    # Should not be 400; null response is fine (no synopsis found)
    assert r.status_code == 200
