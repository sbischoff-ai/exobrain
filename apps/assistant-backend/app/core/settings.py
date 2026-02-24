from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_DEFAULT_MAIN_AGENT_SYSTEM_PROMPT = (
    "You are Exobrain Assistant, a thoughtful general assistant that helps the user through "
    "their day. Maintain continuity across conversation turns, gather notes and ideas, ask "
    "clear follow-up questions when details are missing, and proactively structure information "
    "for later recall. When useful, fact-check claims, suggest lightweight research steps, and "
    "offer practical options to move tasks and projects forward. Keep responses accurate, "
    "concise, and action-oriented while matching the user's tone."
)


class Settings(BaseSettings):
    """Runtime configuration loaded from env vars and local env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str | None = Field(default=None, alias="LOG_LEVEL")
    main_agent_model: str = Field(default="gpt-5.2", alias="MAIN_AGENT_MODEL")
    main_agent_temperature: float = Field(default=0.0, alias="MAIN_AGENT_TEMPERATURE")
    main_agent_system_prompt: str = Field(
        default=_DEFAULT_MAIN_AGENT_SYSTEM_PROMPT,
        alias="MAIN_AGENT_SYSTEM_PROMPT",
    )
    main_agent_use_mock: bool = Field(default=False, alias="MAIN_AGENT_USE_MOCK")
    main_agent_mock_messages_file: str = Field(
        default="mock-data/main-agent-messages.md",
        alias="MAIN_AGENT_MOCK_MESSAGES_FILE",
    )

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

    assistant_cache_redis_url: str = Field(default="redis://localhost:16379/0", alias="ASSISTANT_CACHE_REDIS_URL")
    assistant_cache_key_prefix: str = Field(default="assistant:sessions", alias="ASSISTANT_CACHE_KEY_PREFIX")
    assistant_journal_cache_key_prefix: str = Field(
        default="assistant:journal-cache",
        alias="ASSISTANT_JOURNAL_CACHE_KEY_PREFIX",
    )
    assistant_journal_cache_entry_ttl_seconds: int = Field(default=30, alias="ASSISTANT_JOURNAL_CACHE_ENTRY_TTL_SECONDS")
    assistant_journal_cache_messages_ttl_seconds: int = Field(
        default=20,
        alias="ASSISTANT_JOURNAL_CACHE_MESSAGES_TTL_SECONDS",
    )
    assistant_journal_cache_list_ttl_seconds: int = Field(default=20, alias="ASSISTANT_JOURNAL_CACHE_LIST_TTL_SECONDS")
    assistant_journal_cache_negative_ttl_seconds: int = Field(
        default=8,
        alias="ASSISTANT_JOURNAL_CACHE_NEGATIVE_TTL_SECONDS",
    )
    assistant_journal_cache_jitter_max_seconds: int = Field(
        default=5,
        alias="ASSISTANT_JOURNAL_CACHE_JITTER_MAX_SECONDS",
    )
    exobrain_nats_url: str = Field(default="nats://localhost:14222", alias="EXOBRAIN_NATS_URL")
    jobs_subject_prefix: str = Field(default="jobs", alias="JOBS_SUBJECT_PREFIX")
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    web_tools_use_mock: bool = Field(default=False, alias="WEB_TOOLS_USE_MOCK")
    web_tools_mock_data_file: str | None = Field(default=None, alias="WEB_TOOLS_MOCK_DATA_FILE")

    @property
    def enable_swagger(self) -> bool:
        return self.app_env.lower() == "local"

    @property
    def effective_log_level(self) -> str:
        if self.log_level:
            return self.log_level.upper()
        return "DEBUG" if self.app_env.lower() == "local" else "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
