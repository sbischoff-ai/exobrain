from __future__ import annotations

import pytest

from app.services.user_config_service import InvalidUserConfigValueError, UnknownUserConfigError, UserConfigService


class FakeDatabase:
    def __init__(self) -> None:
        self.definitions_rows = [
            {
                "key": "daily_digest_enabled",
                "config_type": "boolean",
                "description": "Enable daily digest reminders in assistant experiences",
                "default_value": True,
                "option_value": None,
                "option_label": None,
            },
            {
                "key": "answer_verbosity",
                "config_type": "choice",
                "description": "Preferred default answer detail level",
                "default_value": "balanced",
                "option_value": "concise",
                "option_label": "Concise",
            },
            {
                "key": "answer_verbosity",
                "config_type": "choice",
                "description": "Preferred default answer detail level",
                "default_value": "balanced",
                "option_value": "balanced",
                "option_label": "Balanced",
            },
            {
                "key": "answer_verbosity",
                "config_type": "choice",
                "description": "Preferred default answer detail level",
                "default_value": "balanced",
                "option_value": "detailed",
                "option_label": "Detailed",
            },
        ]
        self.overrides_by_user_id: dict[str, dict[str, str]] = {}

    async def fetch(self, query: str, *args: object) -> list[dict[str, object]]:
        if "FROM user_config_definitions" in query:
            return self.definitions_rows
        if "FROM user_config_overrides" in query:
            user_id = str(args[0])
            return [
                {"config_key": key, "config_value": value}
                for key, value in self.overrides_by_user_id.get(user_id, {}).items()
            ]
        raise AssertionError(f"unexpected fetch query: {query}")

    async def execute(self, query: str, *args: object) -> str:
        assert "INSERT INTO user_config_overrides" in query
        user_id = str(args[0])
        keys = [str(key) for key in args[1]]
        values = [str(value) for value in args[2]]
        defaults = [str(default) for default in args[3]]

        overrides = self.overrides_by_user_id.setdefault(user_id, {})
        for key, value, default in zip(keys, values, defaults, strict=True):
            if value == default:
                overrides.pop(key, None)
            else:
                overrides[key] = value

        if not overrides:
            self.overrides_by_user_id.pop(user_id, None)

        return "INSERT 0 1"


@pytest.mark.asyncio
async def test_get_effective_configs_returns_defaults_without_overrides() -> None:
    service = UserConfigService(FakeDatabase())

    configs = await service.get_effective_configs("user-1")

    assert [item.key for item in configs] == ["daily_digest_enabled", "answer_verbosity"]
    assert configs[0].value is True
    assert configs[0].using_default is True
    assert configs[1].value == "balanced"
    assert configs[1].using_default is True


@pytest.mark.asyncio
async def test_update_configs_persists_overrides_and_clears_default_value_override() -> None:
    service = UserConfigService(FakeDatabase())

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
    service = UserConfigService(FakeDatabase())

    with pytest.raises(UnknownUserConfigError):
        await service.update_configs("user-1", {"unknown": True})


@pytest.mark.asyncio
async def test_update_configs_rejects_wrong_type_for_choice() -> None:
    service = UserConfigService(FakeDatabase())

    with pytest.raises(InvalidUserConfigValueError):
        await service.update_configs("user-1", {"answer_verbosity": "invalid-option"})


@pytest.mark.asyncio
async def test_update_configs_rejects_non_boolean_values_for_boolean_type() -> None:
    service = UserConfigService(FakeDatabase())

    with pytest.raises(InvalidUserConfigValueError):
        await service.update_configs("user-1", {"daily_digest_enabled": "false"})
