"""Unit tests for chat service streaming and persistence behavior."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.api.schemas.auth import UnifiedPrincipal
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.journal_service import JournalService


class FakeChatAgent:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._next_index = 0
        self.calls: list[tuple[str, str]] = []

    async def astream(self, message: str, conversation_id: str) -> AsyncIterator[str]:
        self.calls.append((message, conversation_id))
        response = self._responses[self._next_index]
        if self._next_index < len(self._responses) - 1:
            self._next_index += 1
        else:
            self._next_index = 0
        yield response


@pytest.mark.asyncio
async def test_chat_service_stream_message_forwards_conversation_context(fake_database_service) -> None:
    agent = FakeChatAgent(responses=["first", "second"])
    journal_service = JournalService(conversation_service=ConversationService(database=fake_database_service))  # type: ignore[arg-type]
    service = ChatService(agent=agent, journal_service=journal_service)

    first = [chunk async for chunk in service.stream_message("Prompt A", "conv-A")]
    second = [chunk async for chunk in service.stream_message("Prompt B", "conv-B")]

    assert first == ["first"]
    assert second == ["second"]
    assert agent.calls == [("Prompt A", "conv-A"), ("Prompt B", "conv-B")]


@pytest.mark.asyncio
async def test_chat_service_stream_journal_message_persists_user_and_assistant(fake_database_service) -> None:
    agent = FakeChatAgent(responses=["assistant-reply"])
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
    assert agent.calls == [("hello", "conv-1")]


@pytest.mark.asyncio
async def test_fake_chat_agent_cycles_to_first_message_after_reaching_end() -> None:
    """Fake test agent should cycle messages when all configured responses are consumed."""

    agent = FakeChatAgent(responses=["one", "two"])

    first = [chunk async for chunk in agent.astream("ignored", "conv")]
    second = [chunk async for chunk in agent.astream("ignored", "conv")]
    third = [chunk async for chunk in agent.astream("ignored", "conv")]

    assert first == ["one"]
    assert second == ["two"]
    assert third == ["one"]
