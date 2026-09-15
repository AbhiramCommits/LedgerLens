from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_version: str = "0.2.0"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ledgerlens"
    anthropic_api_key: str = ""
    jwt_secret: str = "dev-only-secret"
    jwt_expire_minutes: int = 60


settings = Settings()
