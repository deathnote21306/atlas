from atlas_api.config import Settings


def test_default_dev_config_returns_expected_warnings():
    s = Settings(
        database_url="postgresql+psycopg://x:x@localhost/x",
        _env_file=None,
    )
    warnings = s.validate_for_production()
    assert any("jwt_secret" in w for w in warnings)
    assert any("demo_user_password" in w for w in warnings)
    assert not s.is_production


def test_production_with_default_jwt_secret_would_fail():
    s = Settings(
        environment="production",
        database_url="postgresql+psycopg://x:x@localhost/x",
        _env_file=None,
    )
    assert s.is_production
    warnings = s.validate_for_production()
    assert any("jwt_secret" in w for w in warnings)


def test_properly_configured_settings_returns_no_warnings():
    s = Settings(
        database_url="postgresql+psycopg://x:x@localhost/x",
        jwt_secret="a-real-production-secret",
        demo_user_password="strong-password-123",
        news_poll_enabled=False,
        _env_file=None,
    )
    warnings = s.validate_for_production()
    assert warnings == []
