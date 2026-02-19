"""Unit tests for conversation service database interactions."""

from __future__ import annotations

import pytest

from app.services.conversation_service import ConversationService


class FakeDatabaseService:
    def __init__(self) -> None:
        self.fetchrow_calls: list[tuple[str, tuple]] = []
        self.fetch_calls: list[tuple[str, tuple]] = []
        self.execute_calls: list[tuple[str, tuple]] = []

    async def fetchrow(self, query: str, *args):
        self.fetchrow_calls.append((query, args))
        if "INSERT INTO conversations" in query:
            return {"id": "conv-1"}
        if "INSERT INTO messages" in query:
            return {"id": "msg-1"}
        if "WHERE c.user_id = $1::uuid AND c.reference = $2" in query:
            return {"id": "conv-1", "reference": "2026/02/19"}
        return None

    async def fetch(self, query: str, *args):
        self.fetch_calls.append((query, args))
        return [{"id": "conv-1"}]

    async def execute(self, query: str, *args):
        self.execute_calls.append((query, args))
        return "UPDATE 1"


@pytest.mark.asyncio
async def test_insert_message_updates_conversation_timestamp() -> None:
    db = FakeDatabaseService()
    service = ConversationService(database=db)  # type: ignore[arg-type]

    conversation_id = await service.ensure_conversation("user-1", "2026/02/19")
    message_id = await service.insert_message(
        conversation_id=conversation_id,
        user_id="user-1",
        role="user",
        content="hello",
        client_message_id="00000000-0000-0000-0000-000000000001",
    )

    assert conversation_id == "conv-1"
    assert message_id == "msg-1"
    assert any("UPDATE conversations SET updated_at = NOW()" in query for query, _ in db.execute_calls)


@pytest.mark.asyncio
async def test_query_endpoints_delegate_to_database() -> None:
    db = FakeDatabaseService()
    service = ConversationService(database=db)  # type: ignore[arg-type]

    await service.list_conversations("user-1", limit=10, before=None)
    await service.get_conversation_by_reference("user-1", "2026/02/19")
    await service.list_messages("user-1", "2026/02/19", limit=50)
    await service.search_conversations("user-1", query="hello", limit=5)

    assert len(db.fetch_calls) == 3
    assert len(db.fetchrow_calls) >= 1
