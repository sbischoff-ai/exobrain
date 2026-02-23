"""Unit tests for chat service streaming and persistence behavior."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.api.schemas.auth import UnifiedPrincipal
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.journal_service import JournalService


class FakeChatAgent:
    def __init__(self, responses: list[list[dict[str, object]]]) -> None:
        self._responses = responses
        self._next_index = 0
        self.calls: list[tuple[str, str]] = []

    async def astream(self, message: str, conversation_id: str) -> AsyncIterator[dict[str, object]]:
        self.calls.append((message, conversation_id))
        response = self._responses[self._next_index]
        if self._next_index < len(self._responses) - 1:
            self._next_index += 1
        else:
            self._next_index = 0
        for event in response:
            yield event


@pytest.mark.asyncio
async def test_chat_service_stream_events_forwards_conversation_context(fake_database_service, fake_journal_cache, test_settings) -> None:
    agent = FakeChatAgent(responses=[[{"type": "message_chunk", "data": {"text": "first"}}]])
    journal_service = JournalService(
        conversation_service=ConversationService(database=fake_database_service),  # type: ignore[arg-type]
        cache=fake_journal_cache,  # type: ignore[arg-type]
        settings=test_settings,
    )
    service = ChatService(agent=agent, journal_service=journal_service)

    principal = UnifiedPrincipal(user_id="user-1", email="u@example.com", display_name="User")
    stream_id = await service.start_journal_stream(
        principal=principal,
        message="Prompt A",
        client_message_id="00000000-0000-0000-0000-000000000010",
    )

    events = [event async for event in service.stream_events(stream_id)]

    assert events == [
        {"type": "message_chunk", "data": {"text": "first"}},
        {"type": "done", "data": {"reason": "complete"}},
    ]
    assert agent.calls == [("Prompt A", "conv-1")]


@pytest.mark.asyncio
async def test_chat_service_stream_journal_message_persists_user_and_assistant(fake_database_service, fake_journal_cache, test_settings) -> None:
    agent = FakeChatAgent(
        responses=[[
            {"type": "tool_call", "data": {"tool_call_id": "tc-1", "title": "Web search", "description": "Searching the web for cats"}},
            {"type": "tool_response", "data": {"tool_call_id": "tc-1", "message": "Found 1 candidate source"}},
            {"type": "message_chunk", "data": {"text": "assistant-reply"}},
        ]]
    )
    journal_service = JournalService(
        conversation_service=ConversationService(database=fake_database_service),  # type: ignore[arg-type]
        cache=fake_journal_cache,  # type: ignore[arg-type]
        settings=test_settings,
    )
    service = ChatService(agent=agent, journal_service=journal_service)

    principal = UnifiedPrincipal(user_id="7d6722a0-905e-4e9a-8c1c-4e4504e194f4", email="alice@example.com", display_name="Alice")

    stream_id = await service.start_journal_stream(
        principal=principal,
        message="hello",
        client_message_id="00000000-0000-0000-0000-000000000001",
    )
    _ = [event async for event in service.stream_events(stream_id)]

    assert len(fake_database_service.fetchrow_calls) >= 4
    assert any("INSERT INTO tool_calls" in query for query, _ in fake_database_service.fetchrow_calls)
    assert agent.calls == [("hello", "conv-1")]


@pytest.mark.asyncio
async def test_fake_chat_agent_cycles_to_first_message_after_reaching_end() -> None:
    """Fake test agent should cycle messages when all configured responses are consumed."""

    agent = FakeChatAgent(
        responses=[
            [{"type": "message_chunk", "data": {"text": "one"}}],
            [{"type": "message_chunk", "data": {"text": "two"}}],
        ]
    )

    first = [chunk async for chunk in agent.astream("ignored", "conv")]
    second = [chunk async for chunk in agent.astream("ignored", "conv")]
    third = [chunk async for chunk in agent.astream("ignored", "conv")]

    assert first[0]["data"]["text"] == "one"
    assert second[0]["data"]["text"] == "two"
    assert third[0]["data"]["text"] == "one"
