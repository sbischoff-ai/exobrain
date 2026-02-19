"""Unit tests for chat router streaming edge cases."""

from __future__ import annotations

import pytest

from app.api.routers import chat as chat_router
from app.api.schemas.auth import UnifiedPrincipal


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
            "00000000-0000-0000-0000-000000000001",
            journal,
        )
    ]

    assert chunks == [chat_router.ASSISTANT_STREAM_ERROR_FALLBACK]
    assert len(journal.writes) == 2
    assert journal.writes[0]["role"] == "user"
    assert journal.writes[1]["role"] == "assistant"
