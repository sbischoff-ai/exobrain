from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str | None = Field(default=None, alias="LOG_LEVEL")

    job_orchestrator_db_dsn: str = Field(
        default="postgresql://job_orchestrator:job_orchestrator@localhost:15432/job_orchestrator_db",
        alias="JOB_ORCHESTRATOR_DB_DSN",
    )
    exobrain_nats_url: str = Field(default="nats://localhost:14222", alias="EXOBRAIN_NATS_URL")
    job_queue_subject: str = Field(default="jobs.*.*.requested", alias="JOB_QUEUE_SUBJECT")
    job_events_subject_prefix: str = Field(default="jobs.events", alias="JOB_EVENTS_SUBJECT_PREFIX")
    job_dlq_subject: str = Field(default="jobs.dlq", alias="JOB_DLQ_SUBJECT")
    job_max_attempts: int = Field(default=3, alias="JOB_MAX_ATTEMPTS", ge=1)
    job_dlq_raw_message_max_chars: int = Field(default=4096, alias="JOB_DLQ_RAW_MESSAGE_MAX_CHARS", ge=256)
    job_consumer_durable: str = Field(default="job-orchestrator-worker-v2", alias="JOB_CONSUMER_DURABLE")
    worker_replica_count: int = Field(default=1, alias="WORKER_REPLICA_COUNT", ge=1)
    knowledge_interface_grpc_target: str = Field(
        default="localhost:50051",
        alias="KNOWLEDGE_INTERFACE_GRPC_TARGET",
    )
    knowledge_interface_connect_timeout_seconds: float = Field(
        default=5.0,
        alias="KNOWLEDGE_INTERFACE_CONNECT_TIMEOUT_SECONDS",
        gt=0,
    )
    reshape_schema_query: str = Field(default="", alias="RESHAPE_SCHEMA_QUERY")

    @property
    def effective_log_level(self) -> str:
        if self.log_level:
            return self.log_level
        return "DEBUG" if self.app_env == "local" else "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
