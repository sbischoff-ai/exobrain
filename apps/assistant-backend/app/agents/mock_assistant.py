from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from app.agents.base import ChatAgent


class MockAssistantAgent(ChatAgent):
    """File-driven mock chat agent that cycles through predefined responses."""

    _delimiter = "\n--- message\n"

    def __init__(self, messages_file: str) -> None:
        path = Path(messages_file)
        raw_content = path.read_text(encoding="utf-8")
        parsed_messages = [chunk.strip() for chunk in raw_content.split(self._delimiter)]
        self._messages = [message for message in parsed_messages if message]
        if not self._messages:
            raise ValueError(
                f"No mock messages found in {path}. Use delimiter {self._delimiter!r} between messages."
            )
        self._next_index = 0

    async def stream(self, message: str) -> AsyncIterator[str]:
        del message
        response = self._messages[self._next_index]
        self._next_index = (self._next_index + 1) % len(self._messages)
        yield response
