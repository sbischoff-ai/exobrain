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
    provider_timeout_seconds: float = Field(default=60.0, alias="MODEL_PROVIDER_TIMEOUT_SECONDS")

    @property
    def effective_log_level(self) -> str:
        if self.log_level:
            return self.log_level.upper()
        return "DEBUG" if self.app_env.lower() == "local" else "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
