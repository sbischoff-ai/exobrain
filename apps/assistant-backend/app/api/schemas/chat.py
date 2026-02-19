import uuid

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message to send to the agent")
    client_message_id: uuid.UUID = Field(..., description="Idempotency key for a user message")
