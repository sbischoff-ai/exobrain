from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.api.schemas.users import UserConfigChoiceOption, UserConfigItem


@dataclass(frozen=True)
class ConfigDefinition:
    key: str
    config_type: Literal["boolean", "choice"]
    description: str
    default_value: bool | str
    options: tuple[UserConfigChoiceOption, ...] = ()


class UnknownUserConfigError(ValueError):
    pass


class InvalidUserConfigValueError(ValueError):
    pass


class UserConfigService:
    """Provides effective user config values and validates config updates."""

    _DEFINITIONS: tuple[ConfigDefinition, ...] = (
        ConfigDefinition(
            key="daily_digest_enabled",
            config_type="boolean",
            description="Enable daily digest reminders in assistant experiences",
            default_value=True,
        ),
        ConfigDefinition(
            key="answer_verbosity",
            config_type="choice",
            description="Preferred default answer detail level",
            default_value="balanced",
            options=(
                UserConfigChoiceOption(value="concise", label="Concise"),
                UserConfigChoiceOption(value="balanced", label="Balanced"),
                UserConfigChoiceOption(value="detailed", label="Detailed"),
            ),
        ),
    )

    def __init__(self) -> None:
        self._definitions_by_key: dict[str, ConfigDefinition] = {definition.key: definition for definition in self._DEFINITIONS}
        self._overrides_by_user_id: dict[str, dict[str, bool | str]] = {}

    async def get_effective_configs(self, user_id: str) -> list[UserConfigItem]:
        overrides = self._overrides_by_user_id.get(user_id, {})
        return [self._effective_item(definition, overrides) for definition in self._DEFINITIONS]

    async def update_configs(self, user_id: str, updates: dict[str, bool | str]) -> list[UserConfigItem]:
        for key, value in updates.items():
            definition = self._definitions_by_key.get(key)
            if definition is None:
                raise UnknownUserConfigError(key)
            self._validate(definition, value)

        overrides = self._overrides_by_user_id.setdefault(user_id, {})
        for key, value in updates.items():
            definition = self._definitions_by_key[key]
            if value == definition.default_value:
                overrides.pop(key, None)
            else:
                overrides[key] = value

        if not overrides:
            self._overrides_by_user_id.pop(user_id, None)

        return [self._effective_item(definition, overrides) for definition in self._DEFINITIONS]

    def _validate(self, definition: ConfigDefinition, value: bool | str) -> None:
        if definition.config_type == "boolean":
            if not isinstance(value, bool):
                raise InvalidUserConfigValueError(definition.key)
            return

        if not isinstance(value, str):
            raise InvalidUserConfigValueError(definition.key)
        allowed = {option.value for option in definition.options}
        if value not in allowed:
            raise InvalidUserConfigValueError(definition.key)

    def _effective_item(self, definition: ConfigDefinition, overrides: dict[str, bool | str]) -> UserConfigItem:
        has_override = definition.key in overrides
        effective_value = overrides.get(definition.key, definition.default_value)
        return UserConfigItem(
            key=definition.key,
            config_type=definition.config_type,
            description=definition.description,
            options=list(definition.options),
            value=effective_value,
            default_value=definition.default_value,
            using_default=not has_override,
        )
