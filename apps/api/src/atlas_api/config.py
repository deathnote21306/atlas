from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://atlas:atlas@localhost:5432/atlas"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 480
    demo_user_email: str = "analyst@atlas.local"
    demo_user_password: str = "change-me"
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"


settings = Settings()
