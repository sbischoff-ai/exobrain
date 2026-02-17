from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from env vars and local env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    main_agent_model: str = Field(default="gpt-5.2", alias="MAIN_AGENT_MODEL")
    main_agent_temperature: float = Field(default=0.0, alias="MAIN_AGENT_TEMPERATURE")

    assistant_db_dsn: str = Field(
        default="postgresql://assistant_backend:assistant_backend@localhost:15432/assistant_db",
        alias="ASSISTANT_DB_DSN",
    )
    auth_jwt_secret: str = Field(default="dev-secret-change-me", alias="AUTH_JWT_SECRET")
    auth_jwt_algorithm: str = Field(default="HS256", alias="AUTH_JWT_ALGORITHM")
    auth_access_token_ttl_seconds: int = Field(default=900, alias="AUTH_ACCESS_TOKEN_TTL_SECONDS")
    auth_refresh_token_ttl_seconds: int = Field(default=604800, alias="AUTH_REFRESH_TOKEN_TTL_SECONDS")
    auth_cookie_name: str = Field(default="exobrain_session", alias="AUTH_COOKIE_NAME")
    reshape_schema_query: str = Field(default="", alias="RESHAPE_SCHEMA_QUERY")

    @property
    def enable_swagger(self) -> bool:
        return self.app_env.lower() == "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
