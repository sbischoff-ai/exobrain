import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message text sent to the assistant")
    client_message_id: uuid.UUID = Field(
        ...,
        description="Client-supplied idempotency key so retries do not duplicate persisted user messages",
    )


class ChatMessageStartResponse(BaseModel):
    stream_id: str = Field(..., description="Opaque stream identifier to consume via GET /api/chat/stream/{stream_id}")


class ToolCallEventPayload(BaseModel):
    tool_call_id: str = Field(..., description="Tool-call correlation id for matching response updates")
    title: str = Field(..., description="Short tool activity title")
    description: str = Field(..., description="User-facing detail for current tool work")


class ToolResponseEventPayload(BaseModel):
    tool_call_id: str = Field(..., description="Tool-call correlation id that matches a prior tool_call event")
    message: str = Field(..., description="Short summary of the completed tool result")


class MessageChunkEventPayload(BaseModel):
    text: str = Field(..., description="Incremental assistant markdown/text chunk")


class ErrorEventPayload(BaseModel):
    tool_call_id: str | None = Field(
        default=None,
        description="Tool-call correlation id when the error is tied to a specific tool invocation",
    )
    message: str = Field(..., description="Stream error detail")


class DoneEventPayload(BaseModel):
    reason: str = Field(..., description="Terminal stream status")


class ChatStreamEvent(BaseModel):
    type: Literal["tool_call", "tool_response", "error", "message_chunk", "done"] = Field(
        ...,
        description="SSE event type. Additional event types may be introduced in future versions.",
    )
    data: ToolCallEventPayload | ToolResponseEventPayload | MessageChunkEventPayload | ErrorEventPayload | DoneEventPayload
