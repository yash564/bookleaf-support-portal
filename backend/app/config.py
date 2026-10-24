"""Application settings.

Every secret and environment-specific value is read from the environment (or a local
`.env` file) via pydantic-settings. Nothing here is ever shipped to the frontend.
"""

from functools import lru_cache
from typing import Annotated, Literal

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

    # --- AI. One provider is active at a time; keys never leave the backend. ---
    ai_provider: Literal["auto", "anthropic", "openai"] = "auto"  # auto = anthropic if keyed, else openai
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-5-5"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
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
    def active_provider(self) -> str:
        if self.ai_provider != "auto":
            return self.ai_provider
        return "anthropic" if self.anthropic_api_key else "openai"

    @property
    def active_model(self) -> str:
        return self.openai_model if self.active_provider == "openai" else self.anthropic_model

    @property
    def ai_available(self) -> bool:
        """AI is only attempted when enabled AND the active provider has a key."""
        key = self.openai_api_key if self.active_provider == "openai" else self.anthropic_api_key
        return self.ai_enabled and bool(key)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
