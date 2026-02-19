"""Unit tests for chat service streaming and persistence behavior."""

from __future__ import annotations

import pytest

from app.agents.mock_assistant import MockAssistantAgent
from app.api.schemas.auth import UnifiedPrincipal
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.journal_service import JournalService


@pytest.mark.asyncio
async def test_chat_service_uses_mock_agent_messages_in_order(tmp_path, fake_database_service) -> None:
    """ChatService should return deterministic file-driven mock messages in order."""

    messages_file = tmp_path / "messages.md"
    messages_file.write_text("first\n--- message\nsecond\n", encoding="utf-8")

    agent = MockAssistantAgent(messages_file=str(messages_file))
    journal_service = JournalService(conversation_service=ConversationService(database=fake_database_service))  # type: ignore[arg-type]
    service = ChatService(agent=agent, journal_service=journal_service)

    first = [chunk async for chunk in service.stream_message("Prompt A")]
    second = [chunk async for chunk in service.stream_message("Prompt B")]

    assert first == ["first"]
    assert second == ["second"]


@pytest.mark.asyncio
async def test_chat_service_stream_journal_message_persists_user_and_assistant(tmp_path, fake_database_service) -> None:
    messages_file = tmp_path / "messages.md"
    messages_file.write_text("assistant-reply\n", encoding="utf-8")

    agent = MockAssistantAgent(messages_file=str(messages_file))
    journal_service = JournalService(conversation_service=ConversationService(database=fake_database_service))  # type: ignore[arg-type]
    service = ChatService(agent=agent, journal_service=journal_service)

    principal = UnifiedPrincipal(user_id="7d6722a0-905e-4e9a-8c1c-4e4504e194f4", email="alice@example.com", display_name="Alice")

    chunks = [
        chunk
        async for chunk in service.stream_journal_message(
            principal=principal,
            message="hello",
            client_message_id="00000000-0000-0000-0000-000000000001",
        )
    ]

    assert chunks == ["assistant-reply"]
    assert len(fake_database_service.fetchrow_calls) >= 3


@pytest.mark.asyncio
async def test_mock_agent_cycles_to_first_message_after_reaching_end(tmp_path) -> None:
    """MockAssistantAgent should cycle messages when all configured responses are consumed."""

    messages_file = tmp_path / "messages.md"
    messages_file.write_text("one\n--- message\ntwo\n", encoding="utf-8")

    agent = MockAssistantAgent(messages_file=str(messages_file))

    first = [chunk async for chunk in agent.stream("ignored")]
    second = [chunk async for chunk in agent.stream("ignored")]
    third = [chunk async for chunk in agent.stream("ignored")]

    assert first == ["one"]
    assert second == ["two"]
    assert third == ["one"]
