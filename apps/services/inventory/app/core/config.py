from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    env: str = "local"

    database_url: str
    migration_database_url: str

    # SDD 7.3: /reserve and /release require an "internal token", not a customer
    # JWT - these are internal-only endpoints (SDD 11.1: write endpoints internal).
    internal_service_token: str

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
