"""Unit tests for chat router streaming edge cases."""

from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from app.api.routers import chat as chat_router
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.chat import ChatMessageRequest


class FailingChatService:
    async def stream_message(self, message: str):
        del message
        raise RuntimeError("upstream model failure")
        yield "unreachable"


class FakeJournalService:
    def __init__(self) -> None:
        self.writes: list[dict[str, str]] = []

    def today_reference(self) -> str:
        return "2026/02/19"

    async def ensure_journal(self, user_id: str, reference: str) -> str:
        del user_id, reference
        return "conv-1"

    async def create_journal_message(self, **kwargs) -> str:
        self.writes.append(kwargs)
        return "msg-1"


@pytest.mark.asyncio
async def test_response_stream_yields_fallback_when_agent_stream_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    journal = FakeJournalService()
    principal = UnifiedPrincipal(user_id="user-1", email="u@example.com", display_name="U")

    monkeypatch.setattr(chat_router, "get_chat_service", lambda: FailingChatService())

    chunks = [
        chunk
        async for chunk in chat_router._response_stream(  # noqa: SLF001
            "hello",
            principal,
            "conv-1",
            journal,
        )
    ]

    assert chunks == [chat_router.ASSISTANT_STREAM_ERROR_FALLBACK]
    assert len(journal.writes) == 1
    assert journal.writes[0]["role"] == "assistant"


@pytest.mark.asyncio
async def test_message_persists_user_payload_before_streaming(monkeypatch: pytest.MonkeyPatch) -> None:
    journal = FakeJournalService()
    principal = UnifiedPrincipal(user_id="user-1", email="u@example.com", display_name="U")

    class EmptyChatService:
        async def stream_message(self, message: str):
            del message
            if False:
                yield "noop"

    monkeypatch.setattr(chat_router, "get_chat_service", lambda: EmptyChatService())

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(journal_service=journal)))
    payload = ChatMessageRequest(message="hello", client_message_id=uuid.uuid4())

    response = await chat_router.message(payload=payload, request=request, auth_context=principal)
    assert response.status_code == 200
    assert len(journal.writes) >= 1
    assert journal.writes[0]["role"] == "user"
