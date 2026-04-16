import uuid

from atlas_api.models import Country, User
from atlas_api.security import hash_password


def _seed_user(session):
    u = User(
        id=uuid.uuid4(),
        email="a@b.test",
        password_hash=hash_password("pw-123456"),
        role="Analyst",
    )
    session.add(u)
    session.commit()


def _seed_country(session, iso3: str = "GHA") -> None:
    session.add(Country(
        iso3=iso3, name="Ghana", capital="Accra", region="West Africa",
        tags=["SSA"], tier="C", status="restructured", fx_regime="float",
        fx_regime_notes=None, fx_parallel_premium=None,
    ))
    session.commit()


def _login(client):
    r = client.post("/api/auth/login", json={"email": "a@b.test", "password": "pw-123456"})
    assert r.status_code == 200


def test_list_countries_requires_auth(client):
    r = client.get("/api/countries")
    assert r.status_code == 401


def test_list_countries_returns_seeded(client, session):
    _seed_user(session)
    _seed_country(session, "GHA")
    _seed_country(session, "KEN")
    _login(client)
    r = client.get("/api/countries")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    isos = {c["iso3"] for c in body}
    assert isos == {"GHA", "KEN"}


def test_get_country_returns_full_row(client, session):
    _seed_user(session)
    _seed_country(session, "GHA")
    _login(client)
    r = client.get("/api/countries/GHA")
    assert r.status_code == 200
    body = r.json()
    assert body["iso3"] == "GHA"
    assert body["status"] == "restructured"
    assert body["fx_regime"] == "float"


def test_get_country_404(client, session):
    _seed_user(session)
    _login(client)
    r = client.get("/api/countries/ZZZ")
    assert r.status_code == 404
