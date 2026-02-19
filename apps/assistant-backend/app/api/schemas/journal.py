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


class JournalMessageResponse(BaseModel):
    id: str = Field(..., description="Message identifier")
    role: str = Field(..., description="Message speaker role, e.g. user/assistant")
    content: str | None = Field(default=None, description="Textual message content")
    created_at: datetime = Field(..., description="Message creation timestamp")
    metadata: dict | None = Field(default=None, description="Optional model/runtime metadata")
