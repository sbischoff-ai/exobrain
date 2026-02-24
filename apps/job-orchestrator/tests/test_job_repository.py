from __future__ import annotations

import json

import pytest

from app.contracts import JobEnvelope
from app.job_repository import JobRepository


class FakeDatabase:
    def __init__(self) -> None:
        self.fetchrow_args: tuple[object, ...] | None = None

    async def fetchrow(self, query: str, *args: object):
        self.fetchrow_args = (query, *args)
        return {"job_id": args[0]}


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
