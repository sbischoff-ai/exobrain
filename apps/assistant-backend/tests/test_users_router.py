"""Unit tests for users router with DI container-backed service resolution."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.routers import users as users_router
from app.api.schemas.auth import UnifiedPrincipal, UserResponse
from app.services.contracts import UserServiceProtocol
from tests.conftest import build_test_container, build_test_request


class FakeUserService:
    def __init__(self, user: UserResponse | None) -> None:
        self.user = user
        self.calls: list[str] = []

    async def get_user(self, user_id: str) -> UserResponse | None:
        self.calls.append(user_id)
        return self.user


@pytest.mark.asyncio
async def test_get_me_returns_user_profile() -> None:
    principal = UnifiedPrincipal(user_id="u-1", email="a@example.com", display_name="A")
    user_service = FakeUserService(UserResponse(id="u-1", name="Alice", email="a@example.com"))
    container = build_test_container({UserServiceProtocol: user_service})
    request = build_test_request(container)

    response = await users_router.get_me(request=request, principal=principal)

    assert response.name == "Alice"
    assert response.email == "a@example.com"
    assert user_service.calls == ["u-1"]


@pytest.mark.asyncio
async def test_get_me_rejects_missing_principal() -> None:
    user_service = FakeUserService(UserResponse(id="u-1", name="Alice", email="a@example.com"))
    container = build_test_container({UserServiceProtocol: user_service})
    request = build_test_request(container)

    with pytest.raises(HTTPException) as exc:
        await users_router.get_me(request=request, principal=None)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_me_returns_not_found_when_user_missing() -> None:
    principal = UnifiedPrincipal(user_id="u-missing", email="x@example.com", display_name="X")
    user_service = FakeUserService(None)
    container = build_test_container({UserServiceProtocol: user_service})
    request = build_test_request(container)

    with pytest.raises(HTTPException) as exc:
        await users_router.get_me(request=request, principal=principal)

    assert exc.value.status_code == 404
    assert user_service.calls == ["u-missing"]
