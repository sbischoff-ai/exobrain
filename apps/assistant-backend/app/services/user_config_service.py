from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Literal

from app.api.schemas.users import UserConfigChoiceOption, UserConfigItem
from app.services.contracts import DatabaseServiceProtocol


@dataclass(frozen=True)
class ConfigDefinition:
    id: str
    key: str
    name: str
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

    def __init__(self, database: DatabaseServiceProtocol) -> None:
        self._database = database

    async def get_effective_configs(self, user_id: str) -> list[UserConfigItem]:
        definitions = await self._load_definitions()
        overrides = await self._load_overrides(user_id)
        return [self._effective_item(definition, overrides) for definition in definitions]

    async def update_configs(self, user_id: str, updates: dict[str, bool | str]) -> list[UserConfigItem]:
        definitions = await self._load_definitions()
        definitions_by_key = {definition.key: definition for definition in definitions}

        for key, value in updates.items():
            definition = definitions_by_key.get(key)
            if definition is None:
                raise UnknownUserConfigError(key)
            self._validate(definition, value)

        await self._persist_overrides(user_id, updates, definitions_by_key)
        overrides = await self._load_overrides(user_id)
        return [self._effective_item(definition, overrides) for definition in definitions]

    async def _load_definitions(self) -> list[ConfigDefinition]:
        rows = await self._database.fetch(
            """
            SELECT
              d.id,
              d.key,
              d.name,
              d.config_type,
              d.description,
              d.default_value,
              o.option_value,
              o.option_label,
              o.display_order AS option_display_order
            FROM user_config_definitions d
            LEFT JOIN user_config_choice_options o
              ON o.definition_id = d.id
             AND o.is_active = TRUE
            WHERE d.is_active = TRUE
            ORDER BY d.display_order ASC, d.key ASC, o.display_order ASC, o.option_value ASC
            """
        )

        definitions_by_key: dict[str, ConfigDefinition] = {}
        ordered_keys: list[str] = []
        options_by_key: dict[str, list[UserConfigChoiceOption]] = {}

        for row in rows:
            key = str(row["key"])
            if key not in definitions_by_key:
                raw_config_type = str(row["config_type"])
                default_value = self._deserialize_stored_value(key, row["default_value"])
                if raw_config_type == "boolean":
                    config_type: Literal["boolean", "choice"] = "boolean"
                    default_value = self._coerce_boolean(key, default_value)
                elif raw_config_type == "choice":
                    config_type = "choice"
                    default_value = str(default_value)
                else:
                    raise InvalidUserConfigValueError(key)

                definitions_by_key[key] = ConfigDefinition(
                    id=str(row["id"]),
                    key=key,
                    name=str(row["name"]),
                    config_type=config_type,
                    description=str(row["description"]),
                    default_value=default_value,
                )
                ordered_keys.append(key)

            option_value = row["option_value"]
            if option_value is None:
                continue
            options_by_key.setdefault(key, []).append(
                UserConfigChoiceOption(value=str(option_value), label=str(row["option_label"]))
            )

        definitions: list[ConfigDefinition] = []
        for key in ordered_keys:
            definition = definitions_by_key[key]
            definitions.append(
                ConfigDefinition(
                    id=definition.id,
                    key=definition.key,
                    name=definition.name,
                    config_type=definition.config_type,
                    description=definition.description,
                    default_value=definition.default_value,
                    options=tuple(options_by_key.get(key, [])),
                )
            )
        return definitions

    async def _load_overrides(self, user_id: str) -> dict[str, bool | str]:
        rows = await self._database.fetch(
            """
            SELECT d.key, ucv.value
            FROM user_config_values ucv
            INNER JOIN user_config_definitions d
              ON d.id = ucv.definition_id
            WHERE ucv.user_id = $1::uuid
              AND d.is_active = TRUE
            """,
            user_id,
        )
        return {str(row["key"]): self._deserialize_stored_value(str(row["key"]), row["value"]) for row in rows}

    async def _persist_overrides(
        self,
        user_id: str,
        updates: dict[str, bool | str],
        definitions_by_key: dict[str, ConfigDefinition],
    ) -> None:
        if not updates:
            return

        definition_ids: list[str] = []
        values: list[str] = []
        defaults: list[str] = []
        for key, value in updates.items():
            definition = definitions_by_key[key]
            definition_ids.append(definition.id)
            values.append(self._serialize_value(definition.config_type, value))
            defaults.append(self._serialize_value(definition.config_type, definition.default_value))

        await self._database.execute(
            """
            WITH incoming AS (
              SELECT
                definition_id,
                value_json::jsonb AS value,
                default_json::jsonb AS default_value
              FROM unnest($2::uuid[], $3::text[], $4::text[]) AS t(definition_id, value_json, default_json)
            ),
            removed AS (
              DELETE FROM user_config_values ucv
              USING incoming i
              WHERE ucv.user_id = $1::uuid
                AND ucv.definition_id = i.definition_id
                AND i.value = i.default_value
            )
            INSERT INTO user_config_values (user_id, definition_id, value, updated_at)
            SELECT $1::uuid, i.definition_id, i.value, NOW()
            FROM incoming i
            WHERE i.value <> i.default_value
            ON CONFLICT (user_id, definition_id)
            DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """,
            user_id,
            definition_ids,
            values,
            defaults,
        )

    def _serialize_value(self, config_type: Literal["boolean", "choice"], value: bool | str) -> str:
        return json.dumps({"kind": config_type, "value": value})

    def _deserialize_stored_value(self, key: str, raw: object) -> bool | str:
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise InvalidUserConfigValueError(key) from exc
        if not isinstance(raw, dict):
            raise InvalidUserConfigValueError(key)
        raw_kind = raw.get("kind")
        raw_value = raw.get("value")
        if raw_kind == "boolean":
            return self._coerce_boolean(key, raw_value)
        if raw_kind == "choice" and isinstance(raw_value, str):
            return raw_value
        raise InvalidUserConfigValueError(key)


    def _coerce_boolean(self, key: str, value: bool | str | object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
        raise InvalidUserConfigValueError(key)

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
        if definition.config_type == "boolean":
            effective_value = self._coerce_boolean(definition.key, effective_value)
        return UserConfigItem(
            key=definition.key,
            name=definition.name,
            config_type=definition.config_type,
            description=definition.description,
            options=list(definition.options),
            value=effective_value,
            default_value=definition.default_value,
            using_default=not has_override,
        )
