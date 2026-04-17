import uuid

from atlas_api.models import User
from atlas_api.security import hash_password


def _seed(session):
    session.add(User(
        id=uuid.uuid4(), email="a@b.test",
        password_hash=hash_password("pw-123456"), role="Analyst",
    ))
    session.commit()


def test_logout_clears_cookie(client, session):
    _seed(session)
    login = client.post("/api/auth/login", json={"email": "a@b.test", "password": "pw-123456"})
    assert login.status_code == 200
    assert "atlas_session" in login.cookies
    assert client.get("/api/me").status_code == 200
    r = client.post("/api/auth/logout")
    assert r.status_code == 204
    assert client.get("/api/me").status_code == 401


def test_logout_without_session_still_204(client):
    r = client.post("/api/auth/logout")
    assert r.status_code == 204
