from collections.abc import AsyncIterator

from app.agents.base import ChatAgent


class ChatService:
    """Use-case service for chat messaging."""

    def __init__(self, agent: ChatAgent) -> None:
        self._agent = agent

    async def stream_message(self, message: str) -> AsyncIterator[str]:
        async for chunk in self._agent.stream(message):
            yield chunk
