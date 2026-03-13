"""Unit tests for chat router request orchestration."""

from __future__ import annotations

import uuid

import pytest

from app.api.dependencies.auth import AuthContext
from app.api.routers import chat as chat_router
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.chat import ChatMessageRequest
from app.services.contracts import ChatServiceProtocol
from tests.conftest import build_test_container, build_test_request


class FakeChatService:
    def __init__(self) -> None:
        self.start_calls: list[dict[str, str | None]] = []
        self.stream_calls: list[str] = []

    async def start_journal_stream(
        self,
        *,
        principal,
        message: str,
        client_message_id: str,
        access_token: str | None = None,
        session_id: str | None = None,
    ) -> str:
        self.start_calls.append(
            {
                "principal_id": principal.user_id,
                "message": message,
                "client_message_id": client_message_id,
                "access_token": access_token,
                "session_id": session_id,
            }
        )
        return "stream-123"

    async def stream_events(self, stream_id: str):
        self.stream_calls.append(stream_id)
        yield {"type": "message_chunk", "data": {"text": "ok"}}


@pytest.mark.asyncio
async def test_message_uses_chat_service_from_app_container() -> None:
    service = FakeChatService()
    principal = UnifiedPrincipal(user_id="user-1", email="u@example.com", display_name="U")
    auth_context = AuthContext(principal=principal, access_token="bearer-1", session_id=None)
    container = build_test_container({ChatServiceProtocol: service})
    request = build_test_request(container)
    payload = ChatMessageRequest(message="hello", client_message_id=uuid.uuid4())

    response = await chat_router.message(payload=payload, request=request, auth_context=auth_context)

    assert response.stream_id == "stream-123"
    assert len(service.start_calls) == 1
    assert service.start_calls[0]["principal_id"] == "user-1"
    assert service.start_calls[0]["message"] == "hello"
    assert service.start_calls[0]["access_token"] == "bearer-1"
    assert service.start_calls[0]["session_id"] is None


@pytest.mark.asyncio
async def test_stream_forwards_sse_payload_from_chat_service() -> None:
    service = FakeChatService()
    principal = UnifiedPrincipal(user_id="user-1", email="u@example.com", display_name="U")
    container = build_test_container({ChatServiceProtocol: service})
    request = build_test_request(container)

    response = await chat_router.stream(stream_id="stream-123", request=request, _auth_context=principal)

    body = [chunk async for chunk in response.body_iterator]
    assert "event: message_chunk" in body[0]
    assert service.stream_calls == ["stream-123"]


@pytest.mark.asyncio
async def test_message_threads_session_id_when_bearer_missing() -> None:
    service = FakeChatService()
    principal = UnifiedPrincipal(user_id="user-2", email="s@example.com", display_name="S")
    auth_context = AuthContext(principal=principal, access_token=None, session_id="session-xyz")
    container = build_test_container({ChatServiceProtocol: service})
    request = build_test_request(container)
    payload = ChatMessageRequest(message="hello", client_message_id=uuid.uuid4())

    response = await chat_router.message(payload=payload, request=request, auth_context=auth_context)

    assert response.stream_id == "stream-123"
    assert service.start_calls[0]["access_token"] is None
    assert service.start_calls[0]["session_id"] == "session-xyz"
