from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.settings import Settings
from app.services.knowledge_service import KnowledgeService


class FakeDatabase:
    def __init__(self, rows: list[dict[str, object]], *, user_name: str = "Test User") -> None:
        self.rows = rows
        self.user_name = user_name
        self.fetch_calls: list[tuple[str, tuple[object, ...]]] = []
        self.fetchrow_calls: list[tuple[str, tuple[object, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetch(self, query: str, *args: object):
        self.fetch_calls.append((query, args))
        return self.rows

    async def fetchrow(self, query: str, *args: object):
        self.fetchrow_calls.append((query, args))
        return {"name": self.user_name}

    async def execute(self, query: str, *args: object):
        self.execute_calls.append((query, args))
        return "UPDATE 1"


class FakeJobPublisher:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def enqueue_job(self, *, job_type: str, payload: dict[str, object]) -> str:
        self.calls.append(
            {
                "job_type": job_type,
                "payload": payload,
            }
        )
        return f"job-{len(self.calls)}"


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
    database = FakeDatabase(rows, user_name="Ada")
    publisher = FakeJobPublisher()
    settings = Settings()
    settings.knowledge_update_max_tokens = 100
    service = KnowledgeService(database=database, job_publisher=publisher, settings=settings)

    job_id = await service.enqueue_update_job(user_id="user-1")

    assert job_id == "job-1"
    assert len(publisher.calls) == 3
    assert publisher.calls[0]["payload"]["journal_reference"] == "2026/02/19"
    assert publisher.calls[0]["payload"]["requested_for_user"] == {"user_id": "user-1", "name": "Ada"}
    assert [m["sequence"] for m in publisher.calls[0]["payload"]["messages"]] == [1]
    assert [m["sequence"] for m in publisher.calls[1]["payload"]["messages"]] == [3]
    assert publisher.calls[2]["payload"]["journal_reference"] == "2026/02/20"
    assert database.fetch_calls[0][1] == ("user-1", None)
    assert database.fetchrow_calls[0][1] == ("user-1",)
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
