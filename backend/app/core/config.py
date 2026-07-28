from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="PetroMatch Backend", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/petromatch",
        alias="DATABASE_URL",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    storage_path: Path = Field(default=Path("storage"), alias="STORAGE_PATH")
    request_timeout_seconds: float = Field(default=20.0, alias="REQUEST_TIMEOUT_SECONDS")
    gmail_oauth_client_path: Path = Field(
        default=Path(".secrets/google_oauth_client.json"), alias="GMAIL_OAUTH_CLIENT_PATH"
    )
    gmail_token_path: Path = Field(default=Path(".secrets/gmail_token.json"), alias="GMAIL_TOKEN_PATH")
    gmail_query: str = Field(default="is:unread", alias="GMAIL_QUERY")
    gmail_max_results: int = Field(default=50, alias="GMAIL_MAX_RESULTS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
