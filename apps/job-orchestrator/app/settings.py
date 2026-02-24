from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    job_orchestrator_db_dsn: str = Field(
        default="postgresql://job_orchestrator:job_orchestrator@localhost:15432/job_orchestrator_db",
        alias="JOB_ORCHESTRATOR_DB_DSN",
    )
    exobrain_nats_url: str = Field(default="nats://localhost:14222", alias="EXOBRAIN_NATS_URL")
    job_queue_subject: str = Field(default="jobs.>", alias="JOB_QUEUE_SUBJECT")
    job_events_subject_prefix: str = Field(default="jobs.events", alias="JOB_EVENTS_SUBJECT_PREFIX")
    reshape_schema_query: str = Field(default="", alias="RESHAPE_SCHEMA_QUERY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
