import uuid

from atlas_api.models import User
from atlas_api.security import hash_password


def _seed(session, email: str = "a@b.test", password: str = "pw-123456") -> User:
    u = User(id=uuid.uuid4(), email=email, password_hash=hash_password(password), role="Analyst")
    session.add(u)
    session.commit()
    return u


def test_login_success_sets_cookie(client, session):
    _seed(session)
    r = client.post("/api/auth/login", json={"email": "a@b.test", "password": "pw-123456"})
    assert r.status_code == 200
    assert r.json() == {"email": "a@b.test", "role": "Analyst"}
    assert "atlas_session" in r.cookies


def test_login_wrong_password(client, session):
    _seed(session)
    r = client.post("/api/auth/login", json={"email": "a@b.test", "password": "nope"})
    assert r.status_code == 401


def test_login_unknown_email(client):
    r = client.post("/api/auth/login", json={"email": "ghost@b.test", "password": "whatever"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    r = client.get("/api/me")
    assert r.status_code == 401


def test_me_returns_user_when_authed(client, session):
    _seed(session)
    login = client.post("/api/auth/login", json={"email": "a@b.test", "password": "pw-123456"})
    assert login.status_code == 200
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json() == {"email": "a@b.test", "role": "Analyst"}
