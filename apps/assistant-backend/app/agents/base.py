from typing import AsyncIterator, Protocol

from app.services.chat_stream import ChatStreamEvent


class ChatAgent(Protocol):
    """Contract for chat agents that stream typed chat events."""

    async def astream(self, message: str, conversation_id: str) -> AsyncIterator[ChatStreamEvent]:
        """Stream assistant events for a user message within a conversation."""
