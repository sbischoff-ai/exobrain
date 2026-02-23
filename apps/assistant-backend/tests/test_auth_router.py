"""Unit tests for auth router container-driven resolution."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

from app.api.routers import auth as auth_router
from app.api.schemas.auth import LoginRequest, TokenRefreshRequest, UnifiedPrincipal
from app.core.settings import Settings
from app.services.contracts import AuthServiceProtocol
from tests.conftest import build_test_container, build_test_request


class FakeAuthService:
    def __init__(self) -> None:
        self.login_result: UnifiedPrincipal | None = None
        self.refresh_principal: UnifiedPrincipal | None = None
        self.revoked_refresh: list[str | None] = []
        self.revoked_sessions: list[str | None] = []

    async def login(self, payload: LoginRequest) -> UnifiedPrincipal | None:
        return self.login_result

    async def issue_session(self, principal: UnifiedPrincipal) -> str:
        return "session-123"

    def issue_access_token(self, principal: UnifiedPrincipal) -> str:
        return "access-token"

    async def issue_refresh_token(self, principal: UnifiedPrincipal) -> str:
        return "refresh-token"

    async def principal_from_refresh_token(self, refresh_token: str | None) -> UnifiedPrincipal | None:
        return self.refresh_principal

    async def revoke_refresh_token(self, refresh_token: str | None) -> None:
        self.revoked_refresh.append(refresh_token)

    async def revoke_session(self, session_id: str | None) -> None:
        self.revoked_sessions.append(session_id)


@pytest.mark.asyncio
async def test_login_returns_token_pair_in_api_mode() -> None:
    principal = UnifiedPrincipal(user_id="u-1", email="a@example.com", display_name="A")
    auth_service = FakeAuthService()
    auth_service.login_result = principal
    settings = Settings(AUTH_ACCESS_TOKEN_TTL_SECONDS=123)
    container = build_test_container({AuthServiceProtocol: auth_service, Settings: settings})

    request = build_test_request(container)
    payload = LoginRequest(email="a@example.com", password="password123", session_mode="api", issuance_policy="tokens")

    response = await auth_router.login(payload, request, Response())

    assert response.access_token == "access-token"
    assert response.refresh_token == "refresh-token"
    assert response.expires_in == 123


@pytest.mark.asyncio
async def test_token_refresh_revokes_old_and_issues_new_tokens() -> None:
    principal = UnifiedPrincipal(user_id="u-1", email="a@example.com", display_name="A")
    auth_service = FakeAuthService()
    auth_service.refresh_principal = principal
    settings = Settings(AUTH_ACCESS_TOKEN_TTL_SECONDS=987)
    container = build_test_container({AuthServiceProtocol: auth_service, Settings: settings})

    request = build_test_request(container)
    payload = TokenRefreshRequest(refresh_token="old-refresh-token-123")

    response = await auth_router.token_refresh(payload, request)

    assert auth_service.revoked_refresh == ["old-refresh-token-123"]
    assert response.access_token == "access-token"
    assert response.refresh_token == "refresh-token"
    assert response.expires_in == 987


@pytest.mark.asyncio
async def test_logout_revokes_cookie_session() -> None:
    auth_service = FakeAuthService()
    settings = Settings(AUTH_COOKIE_NAME="session_cookie")
    container = build_test_container({AuthServiceProtocol: auth_service, Settings: settings})

    request = build_test_request(container, cookies={"session_cookie": "cookie-abc"})
    response = Response()

    await auth_router.logout(request, response)

    assert auth_service.revoked_sessions == ["cookie-abc"]


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials() -> None:
    auth_service = FakeAuthService()
    settings = Settings()
    container = build_test_container({AuthServiceProtocol: auth_service, Settings: settings})

    request = build_test_request(container)
    payload = LoginRequest(email="bad@example.com", password="password123", session_mode="api", issuance_policy="tokens")

    with pytest.raises(HTTPException) as exc:
        await auth_router.login(payload, request, Response())

    assert exc.value.status_code == 401
