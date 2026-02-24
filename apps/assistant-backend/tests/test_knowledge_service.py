from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.knowledge_service import KnowledgeService


class FakeJournalService:
    async def list_messages(self, *, user_id: str, journal_reference: str, limit: int, before_sequence: int | None = None):
        assert user_id == "user-1"
        assert journal_reference == "2026/02/19"
        assert limit == 500
        assert before_sequence is None
        return [
            {
                "role": "user",
                "content": "hello",
                "sequence": 1,
                "created_at": datetime(2026, 2, 19, 10, 0, tzinfo=UTC),
            }
        ]


class FakeJobPublisher:
    def __init__(self) -> None:
        self.called_payload: dict[str, object] | None = None

    async def enqueue_job(self, *, job_type: str, correlation_id: str, payload: dict[str, object]) -> str:
        assert job_type == "knowledge.update"
        assert correlation_id == "user-1"
        self.called_payload = payload
        return "job-1"


@pytest.mark.asyncio
async def test_enqueue_update_job_uses_journal_messages() -> None:
    publisher = FakeJobPublisher()
    service = KnowledgeService(FakeJournalService(), publisher)

    job_id = await service.enqueue_update_job(user_id="user-1", journal_reference="2026/02/19")

    assert job_id == "job-1"
    assert publisher.called_payload is not None
    assert publisher.called_payload["journal_reference"] == "2026/02/19"
    assert publisher.called_payload["messages"][0]["content"] == "hello"
