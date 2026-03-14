"""Unit tests for API auth dependency behavior.

These tests verify how request-level auth context is resolved by priority:
1. Bearer token from Authorization header
2. Session cookie fallback
"""

from __future__ import annotations

import pytest

from fastapi import HTTPException

from app.api.dependencies.auth import get_optional_auth_context, get_required_auth_context, get_required_auth_context_with_token
from app.api.schemas.auth import UnifiedPrincipal
from app.core.settings import Settings
from app.services.contracts import AuthServiceProtocol
from tests.conftest import build_test_container, build_test_request


class FakeAuthService:
    """Simple test double that records calls and returns configured principals."""

    def __init__(self, bearer_principal: UnifiedPrincipal | None, session_principal: UnifiedPrincipal | None) -> None:
        self.bearer_principal = bearer_principal
        self.session_principal = session_principal
        self.bearer_tokens_seen: list[str | None] = []
        self.session_ids_seen: list[str | None] = []
        self.issued_access_tokens: list[UnifiedPrincipal] = []

    def principal_from_bearer(self, token: str | None) -> UnifiedPrincipal | None:
        self.bearer_tokens_seen.append(token)
        return self.bearer_principal

    async def principal_from_session(self, session_id: str | None) -> UnifiedPrincipal | None:
        self.session_ids_seen.append(session_id)
        return self.session_principal

    def issue_access_token(self, principal: UnifiedPrincipal) -> str:
        self.issued_access_tokens.append(principal)
        return f"issued-token-for-{principal.user_id}"


@pytest.mark.asyncio
async def test_dependency_prefers_bearer_token_over_cookie() -> None:
    """When both sources exist, bearer auth should win and cookie lookup is skipped."""

    bearer = UnifiedPrincipal(user_id="1", email="a@example.com", display_name="A")
    auth_service = FakeAuthService(bearer_principal=bearer, session_principal=None)
    container = build_test_container({
        AuthServiceProtocol: auth_service,
        Settings: Settings(AUTH_COOKIE_NAME="exobrain_session"),
    })
    request = build_test_request(
        container,
        headers={"authorization": "Bearer valid-token"},
        cookies={"exobrain_session": "session-123"},
    )

    resolved = await get_optional_auth_context(request)

    assert resolved == bearer
    assert auth_service.bearer_tokens_seen == ["valid-token"]
    assert auth_service.session_ids_seen == []


@pytest.mark.asyncio
async def test_dependency_falls_back_to_session_cookie() -> None:
    """If bearer auth is absent or invalid, dependency should attempt session auth."""

    session = UnifiedPrincipal(user_id="2", email="b@example.com", display_name="B")
    auth_service = FakeAuthService(bearer_principal=None, session_principal=session)
    container = build_test_container({
        AuthServiceProtocol: auth_service,
        Settings: Settings(AUTH_COOKIE_NAME="exobrain_session"),
    })
    request = build_test_request(
        container,
        headers={},
        cookies={"exobrain_session": "session-xyz"},
    )

    resolved = await get_optional_auth_context(request)

    assert resolved == session
    assert auth_service.bearer_tokens_seen == [None]
    assert auth_service.session_ids_seen == ["session-xyz"]


@pytest.mark.asyncio
async def test_required_dependency_rejects_missing_auth() -> None:
    auth_service = FakeAuthService(bearer_principal=None, session_principal=None)
    container = build_test_container({
        AuthServiceProtocol: auth_service,
        Settings: Settings(AUTH_COOKIE_NAME="exobrain_session"),
    })
    request = build_test_request(container, headers={}, cookies={})

    with pytest.raises(HTTPException) as exc:
        await get_required_auth_context(request)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_required_auth_context_with_token_returns_bearer_token() -> None:
    bearer = UnifiedPrincipal(user_id="1", email="a@example.com", display_name="A")
    auth_service = FakeAuthService(bearer_principal=bearer, session_principal=None)
    container = build_test_container({
        AuthServiceProtocol: auth_service,
        Settings: Settings(AUTH_COOKIE_NAME="exobrain_session"),
    })
    request = build_test_request(container, headers={"authorization": "Bearer stream-token"}, cookies={})

    resolved = await get_required_auth_context_with_token(request)

    assert resolved.principal == bearer
    assert resolved.access_token == "stream-token"
    assert resolved.session_id is None


@pytest.mark.asyncio
async def test_required_auth_context_with_token_uses_session_without_token() -> None:
    session = UnifiedPrincipal(user_id="2", email="b@example.com", display_name="B")
    auth_service = FakeAuthService(bearer_principal=None, session_principal=session)
    container = build_test_container({
        AuthServiceProtocol: auth_service,
        Settings: Settings(AUTH_COOKIE_NAME="exobrain_session"),
    })
    request = build_test_request(container, headers={}, cookies={"exobrain_session": "session-xyz"})

    resolved = await get_required_auth_context_with_token(request)

    assert resolved.principal == session
    assert resolved.access_token == "issued-token-for-2"
    assert resolved.session_id == "session-xyz"
    assert auth_service.issued_access_tokens == [session]
