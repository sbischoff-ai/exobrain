from typing import AsyncIterator, Protocol


class ChatAgent(Protocol):
    """Contract for chat agents that stream model output."""

    async def astream(self, message: str, conversation_id: str) -> AsyncIterator[str]:
        """Stream response tokens/chunks for a user message within a conversation."""
