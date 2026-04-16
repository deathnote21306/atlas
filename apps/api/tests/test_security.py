from datetime import timedelta

import pytest
from atlas_api.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert verify_password("correct horse battery staple", h) is True
    assert verify_password("wrong", h) is False


def test_jwt_roundtrip():
    token = create_access_token(subject="user-123", expires_delta=timedelta(minutes=5))
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"


def test_jwt_rejects_tampered_token():
    token = create_access_token(subject="user-123", expires_delta=timedelta(minutes=5))
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    with pytest.raises(InvalidTokenError):
        decode_access_token(tampered)


def test_jwt_rejects_expired_token():
    token = create_access_token(subject="user-123", expires_delta=timedelta(seconds=-1))
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)
