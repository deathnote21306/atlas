import uuid
from datetime import UTC, datetime

from atlas_api.models import NewsImpactScore, NewsItem, User
from atlas_api.security import hash_password
from atlas_api.services.news.dedup import url_hash


def _seed_user(session):
    session.add(User(
        id=uuid.uuid4(), email="a@b.test",
        password_hash=hash_password("pw-123456"), role="Analyst",
    ))
    session.commit()


def _login(client):
    r = client.post("/api/auth/login", json={"email": "a@b.test", "password": "pw-123456"})
    assert r.status_code == 200


def _seed_news(session, iso3="GHA"):
    from atlas_api.models import Country
    session.add(Country(
        iso3=iso3, name="Ghana", capital="Accra", region="West Africa",
        tags=["SSA"], tier="C", status="restructured", fx_regime="float",
        fx_regime_notes=None, fx_parallel_premium=None,
    ))
    item = NewsItem(
        id=uuid.uuid4(), url="https://test.com/1",
        url_hash=url_hash("https://test.com/1"),
        title="Ghana debt restructuring", source="reuters",
        published_at=datetime.now(UTC), body_text="Fiscal deficit...",
        primary_iso3=iso3, event_type="Fiscal", ingested_at=datetime.now(UTC),
    )
    session.add(item)
    session.commit()
    score = NewsImpactScore(
        id=uuid.uuid4(), news_item_id=item.id,
        fiscal_impact="H", external_impact="M", fx_impact="L", political_impact="L",
        rationale={"fiscal": "debt keywords"}, scorer="heuristic",
        scored_at=datetime.now(UTC),
    )
    session.add(score)
    session.commit()
    return item


def test_news_list_requires_auth(client):
    r = client.get("/api/news")
    assert r.status_code == 401


def test_news_list_returns_items(client, session):
    _seed_user(session)
    _seed_news(session)
    _login(client)
    r = client.get("/api/news?iso3=GHA")
    assert r.status_code == 200
    body = r.json()
    assert len(body) >= 1
    assert body[0]["title"] == "Ghana debt restructuring"
    assert body[0]["score"]["fiscal_impact"] == "H"


def test_news_get_by_id(client, session):
    _seed_user(session)
    item = _seed_news(session)
    _login(client)
    r = client.get(f"/api/news/{item.id}")
    assert r.status_code == 200
    assert r.json()["url"] == "https://test.com/1"


def test_news_get_404(client, session):
    _seed_user(session)
    _login(client)
    r = client.get(f"/api/news/{uuid.uuid4()}")
    assert r.status_code == 404
