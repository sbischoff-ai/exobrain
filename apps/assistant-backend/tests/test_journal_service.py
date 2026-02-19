"""Unit tests for journal persistence service orchestration."""

from __future__ import annotations

import pytest

from app.services.journal_service import JournalService


class FakeDatabaseService:
    def __init__(self) -> None:
        self.fetchrow_calls: list[tuple[str, tuple]] = []
        self.execute_calls: list[tuple[str, tuple]] = []

    async def fetchrow(self, query: str, *args):
        self.fetchrow_calls.append((query, args))
        if "INSERT INTO conversations" in query:
            return {"id": "conv-1"}
        if "INSERT INTO messages" in query:
            return {"id": "msg-1"}
        return None

    async def execute(self, query: str, *args):
        self.execute_calls.append((query, args))
        return "UPDATE 1"


@pytest.mark.asyncio
async def test_insert_message_updates_conversation_timestamp() -> None:
    db = FakeDatabaseService()
    service = JournalService(database=db)  # type: ignore[arg-type]

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
    assert any("UPDATE conversations SET updated_at = NOW()" in call[0] for call in db.execute_calls)
