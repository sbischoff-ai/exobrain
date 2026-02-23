"""Unit tests for journal service behavior through real internal service dependencies."""

from __future__ import annotations

import pytest

from app.services.conversation_service import ConversationService
from app.services.journal_service import JournalService


@pytest.mark.asyncio
async def test_journal_service_uses_real_conversation_service_flow(
    fake_database_service,
    fake_journal_cache,
    test_settings,
) -> None:
    conversation_service = ConversationService(database=fake_database_service)  # type: ignore[arg-type]
    service = JournalService(
        conversation_service=conversation_service,
        cache=fake_journal_cache,  # type: ignore[arg-type]
        settings=test_settings,
    )

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
    messages = await service.list_messages("user-1", "2026/02/19", limit=100, before_sequence=3)
    search = await service.search_journals("user-1", "hello", limit=5)

    assert conversation_id == "conv-1"
    assert message_id == "msg-1"
    assert journals[0]["id"] == "conv-1"
    assert journal == {"id": "conv-1", "reference": "2026/02/19", "created_at": None, "updated_at": None, "last_message_at": None, "message_count": 0, "status": "open"}
    assert messages[0]["sequence"] == 2
    assert messages[0]["tool_calls"][0]["tool_call_id"] == "tc-1"
    assert search[0]["id"] == "conv-1"
    assert any("UPDATE conversations SET updated_at = NOW()" in query for query, _ in fake_database_service.execute_calls)


@pytest.mark.asyncio
async def test_journal_service_reads_from_cache_after_initial_fetch(
    fake_database_service,
    fake_journal_cache,
    test_settings,
) -> None:
    conversation_service = ConversationService(database=fake_database_service)  # type: ignore[arg-type]
    service = JournalService(
        conversation_service=conversation_service,
        cache=fake_journal_cache,  # type: ignore[arg-type]
        settings=test_settings,
    )

    _ = await service.get_journal("user-1", "2026/02/19")
    first_db_fetchrows = len(fake_database_service.fetchrow_calls)

    second = await service.get_journal("user-1", "2026/02/19")

    assert second is not None
    assert second["reference"] == "2026/02/19"
    assert len(fake_database_service.fetchrow_calls) == first_db_fetchrows
