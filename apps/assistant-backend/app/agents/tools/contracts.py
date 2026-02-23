from __future__ import annotations

from typing import Any, Protocol

from app.services.chat_stream import ChatStreamEvent


class StreamEventMapper(Protocol):
    """Maps tool lifecycle payloads into user-facing stream events."""

    tool_name: str

    def map_tool_call(self, *, tool_call_id: str, args: dict[str, Any]) -> ChatStreamEvent:
        ...

    def map_tool_response(self, *, tool_call_id: str, args: dict[str, Any], result: Any) -> ChatStreamEvent:
        ...

    def map_tool_error(self, *, tool_call_id: str, args: dict[str, Any], error: str) -> ChatStreamEvent:
        ...
