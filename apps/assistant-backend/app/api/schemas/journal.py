from datetime import datetime

from pydantic import BaseModel, Field


class JournalEntryResponse(BaseModel):
    id: str = Field(..., description="Conversation identifier")
    reference: str = Field(..., description="Journal reference in YYYY/MM/DD format")
    created_at: datetime = Field(..., description="Conversation creation timestamp")
    updated_at: datetime = Field(..., description="Conversation update timestamp")
    last_message_at: datetime | None = Field(default=None, description="Timestamp of the newest message")
    message_count: int = Field(..., description="Number of persisted messages in this journal")
    status: str = Field(..., description="Journal status marker for UI rendering")




class ToolCallResponse(BaseModel):
    id: str = Field(..., description="Tool call row identifier")
    tool_call_id: str = Field(..., description="Tool call identifier emitted via SSE")
    title: str = Field(..., description="Human-readable tool execution title")
    description: str = Field(..., description="Tool execution description shown during progress")
    response: str | None = Field(default=None, description="Tool response message shown when execution succeeds")
    error: str | None = Field(default=None, description="Tool error message shown when execution fails")

class JournalMessageResponse(BaseModel):
    id: str = Field(..., description="Message identifier")
    role: str = Field(..., description="Message speaker role, e.g. user/assistant")
    content: str | None = Field(default=None, description="Textual message content")
    sequence: int = Field(..., description="Per-conversation sequence cursor (higher is newer)")
    created_at: datetime = Field(..., description="Message creation timestamp")
    metadata: dict | None = Field(default=None, description="Optional model/runtime metadata")
    tool_calls: list[ToolCallResponse] = Field(default_factory=list, description="Tool-call lifecycle records for this message")
