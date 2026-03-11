from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SelfUserResponse(BaseModel):
    name: str
    email: str


class UserConfigChoiceOption(BaseModel):
    value: str = Field(
        ...,
        description="Stable option identifier accepted by choice config updates",
        examples=["gruvbox-dark", "purple-intelligence"],
    )
    label: str = Field(..., description="Human-friendly label for this choice option", examples=["Gruvbox Dark"])


class UserConfigItem(BaseModel):
    key: str = Field(..., description="Stable configuration key", examples=["frontend.theme"])
    config_type: Literal["boolean", "choice"] = Field(
        ...,
        description="Configuration value type. Supported values: boolean, choice",
        examples=["choice"],
    )
    description: str = Field(
        ...,
        description="What this configuration controls for assistant behavior",
        examples=["Controls the interface theme used in assistant clients"],
    )
    options: list[UserConfigChoiceOption] = Field(
        default_factory=list,
        description="Allowed options for choice configs; empty for boolean configs",
        examples=[[{"value": "gruvbox-dark", "label": "Gruvbox Dark"}, {"value": "purple-intelligence", "label": "Purple Intelligence"}]],
    )
    value: bool | str = Field(
        ...,
        description="Effective value currently applied for the authenticated user",
        examples=["purple-intelligence"],
    )
    default_value: bool | str = Field(
        ...,
        description="Default value used when no user override exists",
        examples=["gruvbox-dark"],
    )
    using_default: bool = Field(
        ...,
        description="True when the effective value falls back to default_value because no override is stored",
        examples=[False],
    )


class UserConfigsResponse(BaseModel):
    configs: list[UserConfigItem] = Field(
        default_factory=list,
        description="All effective user config entries visible to the current authenticated user",
        examples=[
            [
                {
                    "key": "frontend.theme",
                    "config_type": "choice",
                    "description": "Controls the interface theme used in assistant clients",
                    "options": [
                        {"value": "gruvbox-dark", "label": "Gruvbox Dark"},
                        {"value": "purple-intelligence", "label": "Purple Intelligence"},
                    ],
                    "value": "purple-intelligence",
                    "default_value": "gruvbox-dark",
                    "using_default": False,
                }
            ]
        ],
    )


class UserConfigUpdate(BaseModel):
    key: str = Field(..., description="Configuration key to update", examples=["frontend.theme"])
    value: bool | str = Field(
        ...,
        description="New value for the targeted config key",
        examples=["purple-intelligence", True],
    )


class UserConfigsPatchRequest(BaseModel):
    update: UserConfigUpdate | None = Field(
        default=None,
        description="Single config update payload (alternative to updates[] for convenience)",
        examples=[{"key": "frontend.theme", "value": "purple-intelligence"}],
    )
    updates: list[UserConfigUpdate] | None = Field(
        default=None,
        min_length=1,
        description="Batch of one or more config updates applied atomically for the current user",
        examples=[[{"key": "frontend.theme", "value": "purple-intelligence"}]],
    )

    @model_validator(mode="after")
    def validate_update_shape(self) -> UserConfigsPatchRequest:
        if self.update is None and not self.updates:
            raise ValueError("either 'update' or 'updates' must be provided")
        return self

    def normalized_updates(self) -> list[UserConfigUpdate]:
        if self.updates:
            return self.updates
        if self.update is not None:
            return [self.update]
        return []


class UserConfigValidationError(BaseModel):
    key: str = Field(..., description="Configuration key that failed validation", examples=["frontend.theme"])
    message: str = Field(..., description="Validation message for the rejected update", examples=["unsupported choice value"])


class UserConfigsPatchResult(BaseModel):
    updated_configs: list[UserConfigItem] = Field(
        default_factory=list,
        description="Effective config entries after applying accepted updates",
    )
    errors: list[UserConfigValidationError] = Field(
        default_factory=list,
        description="Validation failures for updates that were rejected",
    )
