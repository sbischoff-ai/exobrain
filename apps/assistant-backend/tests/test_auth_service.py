"""Unit tests for authentication service behavior.

These tests focus on the most important auth flows in isolation:
- password hashing and verification invariants
- login success and failure paths
- bearer/session principal resolution
- refresh/session token lifecycle semantics
"""

from __future__ import annotations

import asyncio

import pytest

from app.api.schemas.auth import LoginRequest, UnifiedPrincipal
from app.core.settings import Settings
from app.services.auth_service import AuthService, hash_password, verify_password


class FakeUserService:
    """Minimal async user service stub used to keep tests deterministic."""

    def __init__(self) -> None:
        self._users_by_email: dict[str, dict[str, str]] = {}
        self._users_by_id: dict[str, dict[str, str]] = {}

    def add_user(self, *, user_id: str, email: str, name: str, password_hash: str) -> None:
        record = {"id": user_id, "email": email, "name": name, "password_hash": password_hash}
        self._users_by_email[email] = record
        self._users_by_id[user_id] = record

    async def get_user_by_email(self, email: str):
        return self._users_by_email.get(email)

    async def get_user(self, user_id: str):
        user = self._users_by_id.get(user_id)
        if user is None:
            return None
        return type("User", (), {"id": user["id"], "email": user["email"], "name": user["name"]})


class FakeSessionStore:
    """In-memory async session store test double with TTL handling."""

    def __init__(self) -> None:
        self._sessions: dict[str, tuple[str, float]] = {}

    async def create_session(self, session_id: str, user_id: str, ttl_seconds: int) -> None:
        self._sessions[session_id] = (user_id, asyncio.get_event_loop().time() + ttl_seconds)

    async def get_user_id(self, session_id: str) -> str | None:
        record = self._sessions.get(session_id)
        if record is None:
            return None
        user_id, expires_at = record
        if expires_at <= asyncio.get_event_loop().time():
            self._sessions.pop(session_id, None)
            return None
        return user_id

    async def revoke_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def close(self) -> None:
        return None


@pytest.fixture
def settings() -> Settings:
    """Create a settings object with short TTLs to make expiry behavior easy to test."""

    return Settings(
        APP_ENV="local",
        AUTH_JWT_SECRET="test-secret-with-safe-length-1234567890",
        AUTH_ACCESS_TOKEN_TTL_SECONDS=60,
        AUTH_REFRESH_TOKEN_TTL_SECONDS=1,
    )


@pytest.fixture
def user_service() -> FakeUserService:
    service = FakeUserService()
    service.add_user(
        user_id="7d6722a0-905e-4e9a-8c1c-4e4504e194f4",
        email="alice@example.com",
        name="Alice",
        password_hash=hash_password("password123", salt=b"fixed-salt-for-tests"),
    )
    return service


@pytest.fixture
def session_store() -> FakeSessionStore:
    return FakeSessionStore()


@pytest.fixture
def auth_service(settings: Settings, user_service: FakeUserService, session_store: FakeSessionStore) -> AuthService:
    return AuthService(settings=settings, user_service=user_service, session_store=session_store)


def test_hash_password_produces_verifiable_hash() -> None:
    """A hash generated for a password should validate only that exact password."""

    encoded_hash = hash_password("correct-horse", salt=b"fixed-salt-for-tests")

    assert verify_password("correct-horse", encoded_hash)
    assert not verify_password("wrong-password", encoded_hash)


@pytest.mark.asyncio
async def test_login_returns_principal_for_valid_credentials(auth_service: AuthService) -> None:
    """Given a known user and correct credentials, login should return a principal."""

    principal = await auth_service.login(
        LoginRequest(email="alice@example.com", password="password123")
    )

    assert principal == UnifiedPrincipal(
        user_id="7d6722a0-905e-4e9a-8c1c-4e4504e194f4",
        email="alice@example.com",
        display_name="Alice",
    )


@pytest.mark.asyncio
async def test_login_rejects_unknown_or_wrong_credentials(auth_service: AuthService) -> None:
    """Login must fail for unknown users and for incorrect passwords."""

    unknown_user = await auth_service.login(LoginRequest(email="nobody@example.com", password="password123"))
    wrong_password = await auth_service.login(LoginRequest(email="alice@example.com", password="wrongpass"))

    assert unknown_user is None
    assert wrong_password is None


def test_issue_access_token_roundtrip_returns_same_principal(auth_service: AuthService) -> None:
    """Issued JWT access tokens should decode back into the same principal data."""

    source_principal = UnifiedPrincipal(
        user_id="7d6722a0-905e-4e9a-8c1c-4e4504e194f4",
        email="alice@example.com",
        display_name="Alice",
    )

    token = auth_service.issue_access_token(source_principal)
    decoded_principal = auth_service.principal_from_bearer(token)

    assert decoded_principal == source_principal


def test_principal_from_bearer_returns_none_for_invalid_token(auth_service: AuthService) -> None:
    """Invalid bearer tokens should not raise errors and must resolve to no principal."""

    assert auth_service.principal_from_bearer("this-is-not-a-jwt") is None


@pytest.mark.asyncio
async def test_session_resolution_respects_revocation_and_expiry(
    auth_service: AuthService,
) -> None:
    """Session lookup should work initially, then fail after revoke or expiry."""

    principal = UnifiedPrincipal(
        user_id="7d6722a0-905e-4e9a-8c1c-4e4504e194f4",
        email="alice@example.com",
        display_name="Alice",
    )

    session_id = await auth_service.issue_session(principal)

    # Step 1: Fresh session resolves to a principal.
    resolved = await auth_service.principal_from_session(session_id)
    assert resolved == principal

    # Step 2: Revoked session should not resolve.
    await auth_service.revoke_session(session_id)
    revoked = await auth_service.principal_from_session(session_id)
    assert revoked is None

    # Step 3: Expired session should not resolve.
    expired_session_id = await auth_service.issue_session(principal)
    await asyncio.sleep(1.1)
    expired = await auth_service.principal_from_session(expired_session_id)
    assert expired is None
