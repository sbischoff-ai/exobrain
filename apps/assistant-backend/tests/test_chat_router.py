"""Unit tests for chat router request orchestration."""

from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from app.api.routers import chat as chat_router
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.chat import ChatMessageRequest


class FakeChatService:
    def __init__(self) -> None:
        self.start_calls: list[dict[str, str]] = []
        self.stream_calls: list[str] = []

    async def start_journal_stream(self, *, principal, message: str, client_message_id: str) -> str:
        self.start_calls.append(
            {
                "principal_id": principal.user_id,
                "message": message,
                "client_message_id": client_message_id,
            }
        )
        return "stream-123"

    async def stream_events(self, stream_id: str):
        self.stream_calls.append(stream_id)
        yield {"type": "message_chunk", "data": {"text": "ok"}}


@pytest.mark.asyncio
async def test_message_uses_chat_service_from_app_state() -> None:
    service = FakeChatService()
    principal = UnifiedPrincipal(user_id="user-1", email="u@example.com", display_name="U")
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(chat_service=service)))
    payload = ChatMessageRequest(message="hello", client_message_id=uuid.uuid4())

    response = await chat_router.message(payload=payload, request=request, auth_context=principal)

    assert response.stream_id == "stream-123"
    assert len(service.start_calls) == 1
    assert service.start_calls[0]["principal_id"] == "user-1"
    assert service.start_calls[0]["message"] == "hello"


@pytest.mark.asyncio
async def test_stream_forwards_sse_payload_from_chat_service() -> None:
    service = FakeChatService()
    principal = UnifiedPrincipal(user_id="user-1", email="u@example.com", display_name="U")
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(chat_service=service)))

    response = await chat_router.stream(stream_id="stream-123", request=request, _auth_context=principal)

    body = [chunk async for chunk in response.body_iterator]
    assert "event: message_chunk" in body[0]
    assert service.stream_calls == ["stream-123"]
