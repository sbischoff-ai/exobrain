"""Unit tests for chat service streaming behavior."""

from __future__ import annotations

import pytest

from app.agents.mock_assistant import MockAssistantAgent
from app.services.chat_service import ChatService


@pytest.mark.asyncio
async def test_chat_service_uses_mock_agent_messages_in_order(tmp_path) -> None:
    """ChatService should return deterministic file-driven mock messages in order."""

    messages_file = tmp_path / "messages.md"
    messages_file.write_text("first\n--- message\nsecond\n", encoding="utf-8")

    agent = MockAssistantAgent(messages_file=str(messages_file))
    service = ChatService(agent=agent)

    first = [chunk async for chunk in service.stream_message("Prompt A")]
    second = [chunk async for chunk in service.stream_message("Prompt B")]

    assert first == ["first"]
    assert second == ["second"]


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
