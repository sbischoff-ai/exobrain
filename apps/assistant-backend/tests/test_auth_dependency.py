"""Unit tests for API auth dependency behavior.

These tests verify how request-level auth context is resolved by priority:
1. Bearer token from Authorization header
2. Session cookie fallback
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.dependencies.auth import get_optional_auth_context
from app.api.schemas.auth import UnifiedPrincipal


class FakeAuthService:
    """Simple test double that records calls and returns configured principals."""

    def __init__(self, bearer_principal: UnifiedPrincipal | None, session_principal: UnifiedPrincipal | None) -> None:
        self.bearer_principal = bearer_principal
        self.session_principal = session_principal
        self.bearer_tokens_seen: list[str | None] = []
        self.session_ids_seen: list[str | None] = []

    def principal_from_bearer(self, token: str | None) -> UnifiedPrincipal | None:
        self.bearer_tokens_seen.append(token)
        return self.bearer_principal

    async def principal_from_session(self, session_id: str | None) -> UnifiedPrincipal | None:
        self.session_ids_seen.append(session_id)
        return self.session_principal


class FakeRequest:
    """Request-shaped object with only the attributes the dependency requires."""

    def __init__(self, *, auth_service: FakeAuthService, headers: dict[str, str], cookies: dict[str, str]) -> None:
        self.app = SimpleNamespace(
            state=SimpleNamespace(
                auth_service=auth_service,
                settings=SimpleNamespace(auth_cookie_name="exobrain_session"),
            )
        )
        self.headers = headers
        self.cookies = cookies


@pytest.mark.asyncio
async def test_dependency_prefers_bearer_token_over_cookie() -> None:
    """When both sources exist, bearer auth should win and cookie lookup is skipped."""

    bearer = UnifiedPrincipal(user_id="1", email="a@example.com", display_name="A")
    auth_service = FakeAuthService(bearer_principal=bearer, session_principal=None)
    request = FakeRequest(
        auth_service=auth_service,
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
    request = FakeRequest(
        auth_service=auth_service,
        headers={},
        cookies={"exobrain_session": "session-xyz"},
    )

    resolved = await get_optional_auth_context(request)

    assert resolved == session
    assert auth_service.bearer_tokens_seen == [None]
    assert auth_service.session_ids_seen == ["session-xyz"]
