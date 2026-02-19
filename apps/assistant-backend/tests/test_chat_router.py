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
        self.calls: list[dict[str, str]] = []

    async def stream_journal_message(self, *, principal, message: str, client_message_id: str):
        self.calls.append(
            {
                "principal_id": principal.user_id,
                "message": message,
                "client_message_id": client_message_id,
            }
        )
        yield "ok"


@pytest.mark.asyncio
async def test_message_uses_chat_service_from_app_state() -> None:
    service = FakeChatService()
    principal = UnifiedPrincipal(user_id="user-1", email="u@example.com", display_name="U")
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(chat_service=service)))
    payload = ChatMessageRequest(message="hello", client_message_id=uuid.uuid4())

    response = await chat_router.message(payload=payload, request=request, auth_context=principal)

    body = [chunk async for chunk in response.body_iterator]
    assert body == ["ok"]
    assert len(service.calls) == 1
    assert service.calls[0]["principal_id"] == "user-1"
    assert service.calls[0]["message"] == "hello"
