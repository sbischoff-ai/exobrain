from collections.abc import AsyncIterator
import logging

from app.agents.base import ChatAgent

logger = logging.getLogger(__name__)


class ChatService:
    """Use-case service for chat messaging."""

    def __init__(self, agent: ChatAgent) -> None:
        self._agent = agent

    async def stream_message(self, message: str) -> AsyncIterator[str]:
        logger.debug("streaming chat message", extra={"message_length": len(message)})
        async for chunk in self._agent.stream(message):
            yield chunk
