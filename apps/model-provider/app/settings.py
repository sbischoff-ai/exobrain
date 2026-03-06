from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str | None = Field(default=None, alias="LOG_LEVEL")
    model_provider_config_path: str = Field(default="config/models.yaml", alias="MODEL_PROVIDER_CONFIG_PATH")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    provider_timeout_seconds: float = Field(default=7200.0, alias="MODEL_PROVIDER_TIMEOUT_SECONDS")
    architect_model_max_tokens_per_minute: int = Field(
        default=30000,
        alias="ARCHITECT_MODEL_MAX_TOKENS_PER_MINUTE",
        ge=1,
    )
    openai_max_retries: int = Field(default=8, alias="MODEL_PROVIDER_OPENAI_MAX_RETRIES")
    openai_max_concurrent_requests: int = Field(default=2, alias="MODEL_PROVIDER_OPENAI_MAX_CONCURRENT_REQUESTS")
    anthropic_max_retries: int = Field(default=8, alias="MODEL_PROVIDER_ANTHROPIC_MAX_RETRIES")
    anthropic_max_concurrent_requests: int = Field(
        default=2,
        alias="MODEL_PROVIDER_ANTHROPIC_MAX_CONCURRENT_REQUESTS",
    )

    @property
    def effective_log_level(self) -> str:
        if self.log_level:
            return self.log_level.upper()
        return "DEBUG" if self.app_env.lower() == "local" else "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
