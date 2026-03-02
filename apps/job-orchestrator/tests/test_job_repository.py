from __future__ import annotations

import json

import pytest

from app.contracts import JobEnvelope
from app.job_repository import JobRepository


class FakeDatabase:
    def __init__(self) -> None:
        self.fetchrow_args: tuple[object, ...] | None = None
        self.execute_args: tuple[object, ...] | None = None
        self.next_fetchrow_result: dict[str, object] | None = None

    async def fetchrow(self, query: str, *args: object):
        self.fetchrow_args = (query, *args)
        if self.next_fetchrow_result is not None:
            return self.next_fetchrow_result
        return {"job_id": args[0]}

    async def execute(self, query: str, *args: object):
        self.execute_args = (query, *args)
        return "UPDATE 1"


@pytest.mark.asyncio
async def test_register_requested_serializes_payload_for_jsonb() -> None:
    database = FakeDatabase()
    repository = JobRepository(database)  # type: ignore[arg-type]
    job = JobEnvelope(
        job_id="a4af6654-fcef-4854-a86a-c8b4d237043a",
        job_type="knowledge.update",
        correlation_id="user-1",
        payload={"journal_reference": "2026/02/24", "messages": [{"content": "hello"}]},
        attempt=0,
    )

    inserted = await repository.register_requested(job)

    assert inserted is True
    assert database.fetchrow_args is not None
    payload_arg = database.fetchrow_args[4]
    assert isinstance(payload_arg, str)
    assert json.loads(payload_arg)["journal_reference"] == "2026/02/24"


@pytest.mark.asyncio
async def test_mark_retrying_failure_persists_non_terminal_state() -> None:
    database = FakeDatabase()
    repository = JobRepository(database)  # type: ignore[arg-type]

    await repository.mark_retrying_failure("job-1", "boom")

    assert database.execute_args is not None
    query = str(database.execute_args[0])
    assert "status = 'failed'" in query
    assert "is_terminal = FALSE" in query
    assert database.execute_args[1:] == ("job-1", "boom")


@pytest.mark.asyncio
async def test_mark_terminal_failure_persists_terminal_reason() -> None:
    database = FakeDatabase()
    repository = JobRepository(database)  # type: ignore[arg-type]

    await repository.mark_terminal_failure("job-1", "boom", "max-attempts")

    assert database.execute_args is not None
    query = str(database.execute_args[0])
    assert "is_terminal = TRUE" in query
    assert "terminal_reason = $3" in query
    assert database.execute_args[1:] == ("job-1", "boom", "max-attempts")


@pytest.mark.asyncio
async def test_fetch_status_by_job_id_returns_status_snapshot() -> None:
    database = FakeDatabase()
    database.next_fetchrow_result = {
        "job_id": "job-1",
        "status": "failed",
        "attempt": 3,
        "last_error": "boom",
        "is_terminal": True,
        "terminal_reason": "max-attempts",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    repository = JobRepository(database)  # type: ignore[arg-type]

    status = await repository.fetch_status_by_job_id("job-1")

    assert status == database.next_fetchrow_result
    assert database.fetchrow_args is not None
    query = str(database.fetchrow_args[0])
    assert "is_terminal" in query
    assert "terminal_reason" in query
    assert database.fetchrow_args[1:] == ("job-1",)
