import uuid

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message text sent to the assistant")
    client_message_id: uuid.UUID = Field(
        ...,
        description="Client-supplied idempotency key so retries do not duplicate persisted user messages",
    )
