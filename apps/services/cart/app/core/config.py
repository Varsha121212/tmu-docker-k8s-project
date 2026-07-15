from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    env: str = "local"

    redis_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"

    # Compose DNS is bare service names (SDD 11.2); no trailing slash.
    catalog_service_url: str = "http://catalog:8000"

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
