from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from app.services.grpc import job_orchestrator_pb2

from app.core.settings import Settings
from app.services.knowledge_service import KnowledgeService


class FakeDatabase:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.fetch_calls: list[tuple[str, tuple[object, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetch(self, query: str, *args: object):
        self.fetch_calls.append((query, args))
        return self.rows

    async def execute(self, query: str, *args: object):
        self.execute_calls.append((query, args))
        return "UPDATE 1"


class FakeJobPublisher:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.watch_calls: list[dict[str, object]] = []

    async def enqueue_job(self, *, user_id: str, job_type: str, payload: dict[str, object]) -> str:
        self.calls.append(
            {
                "user_id": user_id,
                "job_type": job_type,
                "payload": payload,
            }
        )
        return f"job-{len(self.calls)}"

    async def watch_job_status(self, *, job_id: str, include_current: bool = True) -> AsyncIterator[job_orchestrator_pb2.JobStatusEvent]:
        self.watch_calls.append({"job_id": job_id, "include_current": include_current})
        yield job_orchestrator_pb2.JobStatusEvent(
            job_id=job_id,
            state=job_orchestrator_pb2.STARTED,
            attempt=1,
            detail="working",
            terminal=False,
            emitted_at="2026-02-19T10:00:00Z",
        )
        yield job_orchestrator_pb2.JobStatusEvent(
            job_id=job_id,
            state=job_orchestrator_pb2.SUCCEEDED,
            attempt=1,
            detail="done",
            terminal=True,
            emitted_at="2026-02-19T10:01:00Z",
        )


@pytest.mark.asyncio
async def test_enqueue_update_job_filters_and_splits_uncommitted_sequences() -> None:
    rows = [
        {
            "id": "m-1",
            "reference": "2026/02/19",
            "role": "user",
            "content": "abcd",
            "sequence": 1,
            "created_at": datetime(2026, 2, 19, 10, 0, tzinfo=UTC),
            "committed_to_knowledge_base": False,
            "previous_committed": None,
        },
        {
            "id": "m-2",
            "reference": "2026/02/19",
            "role": "assistant",
            "content": "abcd",
            "sequence": 2,
            "created_at": datetime(2026, 2, 19, 10, 1, tzinfo=UTC),
            "committed_to_knowledge_base": True,
            "previous_committed": False,
        },
        {
            "id": "m-3",
            "reference": "2026/02/19",
            "role": "user",
            "content": "abcd",
            "sequence": 3,
            "created_at": datetime(2026, 2, 19, 10, 2, tzinfo=UTC),
            "committed_to_knowledge_base": False,
            "previous_committed": True,
        },
        {
            "id": "m-4",
            "reference": "2026/02/20",
            "role": "assistant",
            "content": "abcd",
            "sequence": 1,
            "created_at": datetime(2026, 2, 20, 10, 0, tzinfo=UTC),
            "committed_to_knowledge_base": False,
            "previous_committed": None,
        },
    ]
    database = FakeDatabase(rows)
    publisher = FakeJobPublisher()
    settings = Settings()
    settings.knowledge_update_max_tokens = 100
    service = KnowledgeService(database=database, job_publisher=publisher, settings=settings)

    job_id = await service.enqueue_update_job(user_id="user-1")

    assert job_id == "job-1"
    assert len(publisher.calls) == 3
    assert publisher.calls[0]["payload"]["journal_reference"] == "2026/02/19"
    assert publisher.calls[0]["user_id"] == "user-1"
    assert publisher.calls[0]["payload"]["requested_by_user_id"] == "user-1"
    assert [m["sequence"] for m in publisher.calls[0]["payload"]["messages"]] == [1]
    assert [m["sequence"] for m in publisher.calls[1]["payload"]["messages"]] == [3]
    assert publisher.calls[2]["payload"]["journal_reference"] == "2026/02/20"
    assert database.fetch_calls[0][1] == ("user-1", None)
    assert len(database.execute_calls) == 3


@pytest.mark.asyncio
async def test_enqueue_update_job_respects_token_limit() -> None:
    rows = [
        {
            "id": "m-1",
            "reference": "2026/02/19",
            "role": "user",
            "content": "a" * 24,
            "sequence": 1,
            "created_at": datetime(2026, 2, 19, 10, 0, tzinfo=UTC),
            "committed_to_knowledge_base": False,
            "previous_committed": None,
        },
        {
            "id": "m-2",
            "reference": "2026/02/19",
            "role": "assistant",
            "content": "b" * 24,
            "sequence": 2,
            "created_at": datetime(2026, 2, 19, 10, 1, tzinfo=UTC),
            "committed_to_knowledge_base": False,
            "previous_committed": False,
        },
    ]
    database = FakeDatabase(rows)
    publisher = FakeJobPublisher()
    settings = Settings()
    settings.knowledge_update_max_tokens = 10
    service = KnowledgeService(database=database, job_publisher=publisher, settings=settings)

    await service.enqueue_update_job(user_id="user-1", journal_reference="2026/02/19")

    assert len(publisher.calls) == 2
    assert database.fetch_calls[0][1] == ("user-1", "2026/02/19")


@pytest.mark.asyncio
async def test_enqueue_update_job_returns_empty_when_no_uncommitted_messages() -> None:
    database = FakeDatabase([])
    publisher = FakeJobPublisher()
    service = KnowledgeService(database=database, job_publisher=publisher, settings=Settings())

    job_id = await service.enqueue_update_job(user_id="user-1", journal_reference="2026/02/19")

    assert job_id == ""
    assert publisher.calls == []
    assert database.execute_calls == []


def test_count_text_tokens_rounds_character_division() -> None:
    assert KnowledgeService._count_text_tokens("abcd") == 1
    assert KnowledgeService._count_text_tokens("abcde") == 1
    assert KnowledgeService._count_text_tokens("abcdef") == 2


@pytest.mark.asyncio
async def test_watch_update_job_maps_orchestrator_events_to_stream_events() -> None:
    database = FakeDatabase([])
    publisher = FakeJobPublisher()
    service = KnowledgeService(database=database, job_publisher=publisher, settings=Settings())

    events = [event async for event in service.watch_update_job(job_id="job-1")]

    assert publisher.watch_calls == [{"job_id": "job-1", "include_current": True}]
    assert events == [
        {
            "type": "status",
            "data": {
                "job_id": "job-1",
                "state": "STARTED",
                "attempt": 1,
                "detail": "working",
                "terminal": False,
                "emitted_at": "2026-02-19T10:00:00Z",
            },
        },
        {
            "type": "status",
            "data": {
                "job_id": "job-1",
                "state": "SUCCEEDED",
                "attempt": 1,
                "detail": "done",
                "terminal": True,
                "emitted_at": "2026-02-19T10:01:00Z",
            },
        },
        {
            "type": "done",
            "data": {
                "job_id": "job-1",
                "state": "SUCCEEDED",
                "terminal": True,
            },
        },
    ]
