from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from env vars and local env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    main_agent_model: str = Field(default="gpt-5.2", alias="MAIN_AGENT_MODEL")
    main_agent_temperature: float = Field(default=0.0, alias="MAIN_AGENT_TEMPERATURE")

    @property
    def enable_swagger(self) -> bool:
        return self.app_env.lower() == "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
