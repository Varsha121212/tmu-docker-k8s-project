from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    env: str = "local"

    database_url: str
    migration_database_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"

    # SDD 7.3: sent as X-Internal-Token when calling Inventory's /reserve and
    # /release. MUST be identical to Inventory's INTERNAL_SERVICE_TOKEN.
    internal_service_token: str

    # Compose DNS is bare service names (SDD 11.2).
    cart_service_url: str = "http://cart:8000"
    inventory_service_url: str = "http://inventory:8000"

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
