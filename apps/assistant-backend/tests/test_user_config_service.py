from __future__ import annotations

import pytest

from app.services.user_config_service import InvalidUserConfigValueError, UnknownUserConfigError, UserConfigService


@pytest.mark.asyncio
async def test_get_effective_configs_returns_defaults_without_overrides() -> None:
    service = UserConfigService()

    configs = await service.get_effective_configs("user-1")

    assert [item.key for item in configs] == ["daily_digest_enabled", "answer_verbosity"]
    assert configs[0].value is True
    assert configs[0].using_default is True
    assert configs[1].value == "balanced"
    assert configs[1].using_default is True


@pytest.mark.asyncio
async def test_update_configs_persists_overrides_and_clears_default_value_override() -> None:
    service = UserConfigService()

    updated = await service.update_configs(
        "user-1",
        {
            "daily_digest_enabled": False,
            "answer_verbosity": "detailed",
        },
    )
    reset = await service.update_configs("user-1", {"answer_verbosity": "balanced"})

    by_key = {item.key: item for item in updated}
    assert by_key["daily_digest_enabled"].value is False
    assert by_key["daily_digest_enabled"].using_default is False
    assert by_key["answer_verbosity"].value == "detailed"
    assert by_key["answer_verbosity"].using_default is False

    reset_by_key = {item.key: item for item in reset}
    assert reset_by_key["answer_verbosity"].value == "balanced"
    assert reset_by_key["answer_verbosity"].using_default is True


@pytest.mark.asyncio
async def test_update_configs_rejects_unknown_key() -> None:
    service = UserConfigService()

    with pytest.raises(UnknownUserConfigError):
        await service.update_configs("user-1", {"unknown": True})


@pytest.mark.asyncio
async def test_update_configs_rejects_wrong_type_for_choice() -> None:
    service = UserConfigService()

    with pytest.raises(InvalidUserConfigValueError):
        await service.update_configs("user-1", {"answer_verbosity": "invalid-option"})
