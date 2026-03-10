from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str | None = Field(default=None, alias="LOG_LEVEL")
    mcp_server_host: str = Field(default="0.0.0.0", alias="MCP_SERVER_HOST")
    mcp_server_port: int = Field(default=8090, alias="MCP_SERVER_PORT", ge=1, le=65535)
    web_search_provider: Literal["auto", "static", "tavily"] = Field(default="auto", alias="WEB_SEARCH_PROVIDER")
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    tavily_base_url: str = Field(default="https://api.tavily.com", alias="TAVILY_BASE_URL")
    enabled_tool_categories: tuple[str, ...] = Field(default=("utility", "web"), alias="ENABLED_TOOL_CATEGORIES")
    enable_utility_tools: bool = Field(default=True, alias="ENABLE_UTILITY_TOOLS")
    enable_web_tools: bool = Field(default=True, alias="ENABLE_WEB_TOOLS")

    @field_validator("enabled_tool_categories", mode="before")
    @classmethod
    def parse_enabled_tool_categories(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @property
    def effective_log_level(self) -> str:
        if self.log_level:
            return self.log_level.upper()
        return "DEBUG" if self.app_env.lower() == "local" else "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
