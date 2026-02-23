from __future__ import annotations

import json
from typing import Literal, TypedDict


class ToolCallEventData(TypedDict):
    tool_call_id: str
    title: str
    description: str


class ToolResponseEventData(TypedDict):
    tool_call_id: str
    message: str


class ErrorEventData(TypedDict):
    message: str
    tool_call_id: str | None


class MessageChunkEventData(TypedDict):
    text: str


class DoneEventData(TypedDict):
    reason: str


ChatStreamEventType = Literal["tool_call", "tool_response", "error", "message_chunk", "done"]


class ChatStreamEvent(TypedDict):
    type: ChatStreamEventType
    data: ToolCallEventData | ToolResponseEventData | ErrorEventData | MessageChunkEventData | DoneEventData


def encode_sse_event(event: ChatStreamEvent) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
