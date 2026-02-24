from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
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


class JobResultEvent(BaseModel):
    schema_version: int = Field(default=1)
    job_id: str
    job_type: str
    status: str
    correlation_id: str
    attempt: int
    detail: str | None = None
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
