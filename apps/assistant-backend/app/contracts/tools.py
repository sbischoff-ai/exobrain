from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolMetadata(BaseModel):
    """Static metadata contract for one registered tool."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    json_schema: dict[str, Any] = Field(default_factory=dict)


class ToolInvocationCorrelation(BaseModel):
    """Cross-service correlation fields attached to one tool invocation."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    conversation_id: str | None = None
    tool_call_id: str | None = None


class ToolInvocationEnvelope(BaseModel):
    """Runtime envelope for a single tool invocation request."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)
    correlation: ToolInvocationCorrelation


class ToolExecutionError(BaseModel):
    """Typed error payload emitted by tool adapters."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


ToolResultT = TypeVar("ToolResultT")


class ToolResultEnvelope(BaseModel, Generic[ToolResultT]):
    """Typed result envelope for tool execution outcomes."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "error"]
    result: ToolResultT | None = None
    error: ToolExecutionError | None = None

    @model_validator(mode="after")
    def _validate_result_or_error(self) -> ToolResultEnvelope[ToolResultT]:
        if self.status == "ok":
            if self.error is not None:
                raise ValueError("error must be omitted for ok status")
            return self

        if self.error is None:
            raise ValueError("error is required for error status")
        if self.result is not None:
            raise ValueError("result must be omitted for error status")
        return self
