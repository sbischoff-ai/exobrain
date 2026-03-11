from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SelfUserResponse(BaseModel):
    name: str
    email: str


class UserConfigChoiceOption(BaseModel):
    value: str = Field(..., description="Stable option identifier accepted by choice config updates")
    label: str = Field(..., description="Human-friendly label for this choice option")


class UserConfigItem(BaseModel):
    key: str = Field(..., description="Stable configuration key")
    config_type: Literal["boolean", "choice"] = Field(
        ..., description="Configuration value type. Supported values: boolean, choice"
    )
    description: str = Field(..., description="What this configuration controls for assistant behavior")
    options: list[UserConfigChoiceOption] = Field(
        default_factory=list,
        description="Allowed options for choice configs; empty for boolean configs",
    )
    value: bool | str = Field(..., description="Effective value currently applied for the authenticated user")
    default_value: bool | str = Field(..., description="Default value used when no user override exists")
    using_default: bool = Field(
        ..., description="True when the effective value falls back to default_value because no override is stored"
    )


class UserConfigsResponse(BaseModel):
    configs: list[UserConfigItem] = Field(
        default_factory=list,
        description="All effective user config entries visible to the current authenticated user",
    )


class UserConfigUpdate(BaseModel):
    key: str = Field(..., description="Configuration key to update")
    value: bool | str = Field(..., description="New value for the targeted config key")


class UserConfigsPatchRequest(BaseModel):
    updates: list[UserConfigUpdate] = Field(
        ...,
        min_length=1,
        description="One or more config updates applied atomically for the current user",
    )
