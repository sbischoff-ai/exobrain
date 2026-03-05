from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    content: Any
    is_error: bool = False


class ToolCallBlock(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


MessageBlock = Annotated[TextBlock | ToolResultBlock | ToolCallBlock, Field(discriminator="type")]


class SystemMessage(BaseModel):
    role: Literal["system"] = "system"
    content: list[TextBlock]


class UserMessage(BaseModel):
    role: Literal["user"] = "user"
    content: list[TextBlock | ToolResultBlock]


class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: list[TextBlock | ToolCallBlock]


InputMessage = Annotated[SystemMessage | UserMessage | AssistantMessage, Field(discriminator="role")]


class FunctionToolDefinition(BaseModel):
    type: Literal["function"] = "function"
    name: str
    description: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolChoiceAuto(BaseModel):
    type: Literal["auto"] = "auto"


class ToolChoiceNone(BaseModel):
    type: Literal["none"] = "none"


class ToolChoiceAny(BaseModel):
    type: Literal["required"] = "required"


class ToolChoiceTool(BaseModel):
    type: Literal["tool"] = "tool"
    name: str


ToolChoicePolicy = Annotated[ToolChoiceAuto | ToolChoiceNone | ToolChoiceAny | ToolChoiceTool, Field(discriminator="type")]


class StructuredOutputIntent(BaseModel):
    name: str | None = None
    json_schema: dict[str, Any] = Field(alias="schema")
    strict: bool = False


class NativeChatRequest(BaseModel):
    model: str
    messages: list[InputMessage]
    tools: list[FunctionToolDefinition] = Field(default_factory=list)
    tool_choice: ToolChoicePolicy | None = None
    structured_output: StructuredOutputIntent | None = None
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class NativeChatResponse(BaseModel):
    id: str
    model: str
    message: AssistantMessage
    finish_reason: str | None = None
    usage: Usage = Field(default_factory=Usage)


class TextDeltaFrame(BaseModel):
    type: Literal["text_delta"] = "text_delta"
    text: str


class ToolCallFrame(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    index: int = 0
    arguments: dict[str, Any] = Field(default_factory=dict)


class CompletionFrame(BaseModel):
    type: Literal["completion"] = "completion"
    finish_reason: str | None = None


class UsageFrame(BaseModel):
    type: Literal["usage"] = "usage"
    usage: Usage


StreamFrame = Annotated[TextDeltaFrame | ToolCallFrame | CompletionFrame | UsageFrame, Field(discriminator="type")]
