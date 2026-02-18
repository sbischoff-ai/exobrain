"""Unit tests for chat service streaming behavior."""

from __future__ import annotations

import pytest

from app.services.chat_service import ChatService


class FakeChatAgent:
    """Agent double that yields deterministic chunks for stream testing."""

    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks
        self.messages_seen: list[str] = []

    async def stream(self, message: str):
        self.messages_seen.append(message)
        for chunk in self.chunks:
            yield chunk


@pytest.mark.asyncio
async def test_chat_service_yields_agent_chunks_in_order() -> None:
    """ChatService should transparently forward streamed chunks from the agent."""

    agent = FakeChatAgent(chunks=["hello", " ", "world"])
    service = ChatService(agent=agent)

    collected = [chunk async for chunk in service.stream_message("Say hi")]

    assert collected == ["hello", " ", "world"]
    assert agent.messages_seen == ["Say hi"]
