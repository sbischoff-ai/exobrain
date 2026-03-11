from __future__ import annotations

import json

import pytest

from app.services.user_config_service import InvalidUserConfigValueError, UnknownUserConfigError, UserConfigService


class FakeDatabase:
    def __init__(self) -> None:
        self.definitions_rows = [
            {
                "id": "00000000-0000-0000-0000-000000000101",
                "key": "daily_digest_enabled",
                "config_type": "boolean",
                "description": "Enable daily digest reminders in assistant experiences",
                "default_value": {"kind": "boolean", "value": True},
                "option_value": None,
                "option_label": None,
            },
            {
                "id": "00000000-0000-0000-0000-000000000102",
                "key": "answer_verbosity",
                "config_type": "choice",
                "description": "Preferred default answer detail level",
                "default_value": {"kind": "choice", "value": "balanced"},
                "option_value": "concise",
                "option_label": "Concise",
            },
            {
                "id": "00000000-0000-0000-0000-000000000102",
                "key": "answer_verbosity",
                "config_type": "choice",
                "description": "Preferred default answer detail level",
                "default_value": {"kind": "choice", "value": "balanced"},
                "option_value": "balanced",
                "option_label": "Balanced",
            },
            {
                "id": "00000000-0000-0000-0000-000000000102",
                "key": "answer_verbosity",
                "config_type": "choice",
                "description": "Preferred default answer detail level",
                "default_value": {"kind": "choice", "value": "balanced"},
                "option_value": "detailed",
                "option_label": "Detailed",
            },
        ]
        self.definition_id_by_key = {
            "daily_digest_enabled": "00000000-0000-0000-0000-000000000101",
            "answer_verbosity": "00000000-0000-0000-0000-000000000102",
        }
        self.key_by_definition_id = {value: key for key, value in self.definition_id_by_key.items()}
        self.overrides_by_user_id: dict[str, dict[str, bool | str]] = {}

    async def fetch(self, query: str, *args: object) -> list[dict[str, object]]:
        if "FROM user_config_definitions" in query:
            return self.definitions_rows
        if "FROM user_config_values" in query:
            user_id = str(args[0])
            return [
                {"key": key, "value": {"kind": "boolean", "value": value} if isinstance(value, bool) else {"kind": "choice", "value": value}}
                for key, value in self.overrides_by_user_id.get(user_id, {}).items()
            ]
        raise AssertionError(f"unexpected fetch query: {query}")

    async def execute(self, query: str, *args: object) -> str:
        assert "INSERT INTO user_config_values" in query
        user_id = str(args[0])
        definition_ids = [str(definition_id) for definition_id in args[1]]
        values = [json.loads(str(value_json)) for value_json in args[2]]
        defaults = [json.loads(str(default_json)) for default_json in args[3]]

        overrides = self.overrides_by_user_id.setdefault(user_id, {})
        for definition_id, value, default in zip(definition_ids, values, defaults, strict=True):
            key = self.key_by_definition_id[definition_id]
            value_data = value["value"]
            default_data = default["value"]
            if value_data == default_data:
                overrides.pop(key, None)
            else:
                overrides[key] = value_data

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
