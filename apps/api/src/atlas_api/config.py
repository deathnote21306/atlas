from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
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
    ai_model: str = "claude-sonnet-4-5"
    ai_daily_token_cap: int = 200_000

    # -- Comtrade (Phase 3a) --
    comtrade_api_key: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def validate_for_production(self) -> list[str]:
        warnings: list[str] = []
        if self.jwt_secret == "dev-secret-change-me":
            warnings.append("jwt_secret is still the default dev value")
        if self.anthropic_api_key == "" and self.news_poll_enabled:
            warnings.append("anthropic_api_key is empty but news_poll_enabled is True")
        if self.demo_user_password == "change-me":
            warnings.append("demo_user_password is still the default dev value")
        return warnings


settings = Settings()
