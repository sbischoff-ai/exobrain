from __future__ import annotations

import json
from typing import Literal, TypedDict


class ToolCallEventData(TypedDict):
    title: str
    description: str


class ToolResponseEventData(TypedDict):
    message: str


class ErrorEventData(TypedDict):
    message: str


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
