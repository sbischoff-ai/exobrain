from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field


class JobEnvelope(BaseModel):
    schema_version: int = Field(default=1)
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    job_type: str
    correlation_id: str
    payload: dict[str, Any]
    attempt: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeUpdateMessage(BaseModel):
    role: str
    content: str | None = None
    sequence: int | None = None
    created_at: str | None = None


class KnowledgeUpdatePayload(BaseModel):
    journal_reference: str
    messages: list[KnowledgeUpdateMessage]
    requested_by_user_id: str


class JobResultEvent(BaseModel):
    schema_version: int = Field(default=1)
    job_id: str
    job_type: str
    status: str
    correlation_id: str
    attempt: int
    detail: str | None = None
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JobStatusEvent(BaseModel):
    schema_version: int = Field(default=1)
    job_id: str
    state: str
    attempt: int
    detail: str | None = None
    terminal: bool
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeadLetterEvent(BaseModel):
    schema_version: int = Field(default=1)
    reason: str
    detail: str
    raw_message: str
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkerJobRunnerProtocol(Protocol):
    async def run_job(self, job: JobEnvelope) -> None:
        """Execute a single job in a worker runtime."""
