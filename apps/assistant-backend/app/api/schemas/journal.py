from datetime import datetime

from pydantic import BaseModel


class JournalEntryResponse(BaseModel):
    id: str
    reference: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None
    message_count: int
    status: str


class JournalMessageResponse(BaseModel):
    id: str
    role: str
    content: str | None
    created_at: datetime
    metadata: dict | None = None
