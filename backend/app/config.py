"""Application settings.

Every secret and environment-specific value is read from the environment (or a local
`.env` file) via pydantic-settings. Nothing here is ever shipped to the frontend.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://bookleaf:bookleaf@localhost:5433/bookleaf"

    jwt_secret: str = Field(min_length=32, description="HMAC key; 32+ bytes per RFC 7518")
    jwt_expires_minutes: int = 60 * 24 * 7
    jwt_algorithm: str = "HS256"

    # NoDecode: read the raw "a,b,c" string from env and split it ourselves (see validator).
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-5-5"
    ai_enabled: bool = True
    ai_timeout_seconds: float = 20.0
    ai_max_retries: int = 2

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def ai_available(self) -> bool:
        """AI is only attempted when enabled AND a key is configured."""
        return self.ai_enabled and bool(self.anthropic_api_key)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
