"""Unit tests for journal service orchestration over conversation service."""

from __future__ import annotations

import pytest

from app.services.journal_service import JournalService


class FakeConversationService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    async def ensure_conversation(self, user_id: str, reference: str) -> str:
        self.calls.append(("ensure_conversation", (user_id, reference), {}))
        return "conv-1"

    async def insert_message(self, **kwargs) -> str:
        self.calls.append(("insert_message", (), kwargs))
        return "msg-1"

    async def list_conversations(self, user_id: str, limit: int, before: str | None = None):
        self.calls.append(("list_conversations", (user_id, limit, before), {}))
        return [{"id": "conv-1"}]

    async def get_conversation_by_reference(self, user_id: str, reference: str):
        self.calls.append(("get_conversation_by_reference", (user_id, reference), {}))
        return {"id": "conv-1", "reference": reference}

    async def list_messages(self, user_id: str, reference: str, limit: int):
        self.calls.append(("list_messages", (user_id, reference, limit), {}))
        return [{"id": "msg-1"}]

    async def search_conversations(self, user_id: str, query: str, limit: int):
        self.calls.append(("search_conversations", (user_id, query, limit), {}))
        return [{"id": "conv-1"}]


@pytest.mark.asyncio
async def test_journal_service_delegates_to_conversation_service() -> None:
    conversation_service = FakeConversationService()
    service = JournalService(conversation_service=conversation_service)  # type: ignore[arg-type]

    conversation_id = await service.ensure_journal("user-1", "2026/02/19")
    message_id = await service.create_journal_message(
        conversation_id=conversation_id,
        user_id="user-1",
        role="user",
        content="hello",
        client_message_id="00000000-0000-0000-0000-000000000001",
    )
    journals = await service.list_journals("user-1", limit=20)
    journal = await service.get_journal("user-1", "2026/02/19")
    today_journal = await service.get_today_journal("user-1", create=False)
    messages = await service.list_messages("user-1", "2026/02/19", limit=100)
    today_messages = await service.list_today_messages("user-1", limit=100)
    search = await service.search_journals("user-1", "hello", limit=5)

    assert conversation_id == "conv-1"
    assert message_id == "msg-1"
    assert journals == [{"id": "conv-1"}]
    assert journal == {"id": "conv-1", "reference": "2026/02/19"}
    assert today_journal is not None
    assert messages == [{"id": "msg-1"}]
    assert today_messages == [{"id": "msg-1"}]
    assert search == [{"id": "conv-1"}]
