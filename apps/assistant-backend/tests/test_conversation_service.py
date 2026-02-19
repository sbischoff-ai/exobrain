"""Unit tests for conversation service database interactions."""

from __future__ import annotations

import pytest

from app.services.conversation_service import ConversationService


@pytest.mark.asyncio
async def test_insert_message_updates_conversation_timestamp(fake_database_service) -> None:
    service = ConversationService(database=fake_database_service)  # type: ignore[arg-type]

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
    assert any("UPDATE conversations SET updated_at = NOW()" in query for query, _ in fake_database_service.execute_calls)


@pytest.mark.asyncio
async def test_query_endpoints_delegate_to_database(fake_database_service) -> None:
    service = ConversationService(database=fake_database_service)  # type: ignore[arg-type]

    await service.list_conversations("user-1", limit=10, before=None)
    await service.get_conversation_by_reference("user-1", "2026/02/19")
    await service.list_messages("user-1", "2026/02/19", limit=50)
    await service.search_conversations("user-1", query="hello", limit=5)

    assert len(fake_database_service.fetch_calls) == 3
    assert len(fake_database_service.fetchrow_calls) >= 1
