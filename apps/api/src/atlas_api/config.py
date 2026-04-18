from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://atlas:atlas@localhost:5433/atlas"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 480
    demo_user_email: str = "analyst@atlas.test"
    demo_user_password: str = "change-me"
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"
    ingestion_schedule_enabled: bool = True
    ingestion_cron: str = "0 3 * * *"  # 03:00 UTC daily
    news_poll_enabled: bool = False
    news_poll_cron: str = "*/10 * * * *"  # every 10 minutes

    # -- AI integration (Plan 5b) --
    anthropic_api_key: str = ""
    ai_model: str = "claude-sonnet-4-5-20250514"
    ai_daily_token_cap: int = 200_000


settings = Settings()
