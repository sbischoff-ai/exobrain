"""Unit tests for users router with DI container-backed service resolution."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.routers import users as users_router
from app.api.schemas.auth import UnifiedPrincipal, UserResponse
from app.api.schemas.users import UserConfigChoiceOption, UserConfigItem, UserConfigsPatchRequest, UserConfigUpdate
from app.services.contracts import UserConfigServiceProtocol, UserServiceProtocol
from tests.conftest import build_test_container, build_test_request


class FakeUserService:
    def __init__(self, user: UserResponse | None) -> None:
        self.user = user
        self.calls: list[str] = []

    async def get_user(self, user_id: str) -> UserResponse | None:
        self.calls.append(user_id)
        return self.user


class FakeUserConfigService:
    def __init__(self) -> None:
        self.get_calls: list[str] = []
        self.update_calls: list[tuple[str, dict[str, bool | str]]] = []

    async def get_effective_configs(self, user_id: str) -> list[UserConfigItem]:
        self.get_calls.append(user_id)
        return [
            UserConfigItem(
                key="answer_verbosity",
                config_type="choice",
                description="Preferred answer detail level",
                options=[
                    UserConfigChoiceOption(value="concise", label="Concise"),
                    UserConfigChoiceOption(value="balanced", label="Balanced"),
                ],
                value="balanced",
                default_value="balanced",
                using_default=True,
            )
        ]

    async def update_configs(self, user_id: str, updates: dict[str, bool | str]) -> list[UserConfigItem]:
        self.update_calls.append((user_id, updates))
        return [
            UserConfigItem(
                key="daily_digest_enabled",
                config_type="boolean",
                description="Enable daily digest reminders",
                value=bool(updates["daily_digest_enabled"]),
                default_value=True,
                using_default=False,
            )
        ]


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


@pytest.mark.asyncio
async def test_get_me_configs_returns_effective_configs() -> None:
    principal = UnifiedPrincipal(user_id="u-1", email="a@example.com", display_name="A")
    config_service = FakeUserConfigService()
    container = build_test_container({UserConfigServiceProtocol: config_service})
    request = build_test_request(container)

    response = await users_router.get_me_configs(request=request, principal=principal)

    assert len(response.configs) == 1
    assert response.configs[0].key == "answer_verbosity"
    assert config_service.get_calls == ["u-1"]


@pytest.mark.asyncio
async def test_patch_me_configs_updates_multiple_keys() -> None:
    principal = UnifiedPrincipal(user_id="u-1", email="a@example.com", display_name="A")
    config_service = FakeUserConfigService()
    container = build_test_container({UserConfigServiceProtocol: config_service})
    request = build_test_request(container)
    payload = UserConfigsPatchRequest(
        updates=[
            UserConfigUpdate(key="daily_digest_enabled", value=False),
            UserConfigUpdate(key="answer_verbosity", value="concise"),
        ]
    )

    response = await users_router.patch_me_configs(payload=payload, request=request, principal=principal)

    assert response.configs[0].key == "daily_digest_enabled"
    assert config_service.update_calls == [
        (
            "u-1",
            {
                "daily_digest_enabled": False,
                "answer_verbosity": "concise",
            },
        )
    ]
