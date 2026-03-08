from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EchoToolInput(StrictModel):
    text: str = Field(min_length=1)


class EchoToolOutput(StrictModel):
    text: str


class AddToolInput(StrictModel):
    a: int
    b: int


class AddToolOutput(StrictModel):
    sum: int


class EchoToolInvocation(StrictModel):
    name: Literal["echo"]
    arguments: EchoToolInput


class AddToolInvocation(StrictModel):
    name: Literal["add"]
    arguments: AddToolInput


ToolInvocation = EchoToolInvocation | AddToolInvocation


class EchoToolResult(StrictModel):
    name: Literal["echo"]
    result: EchoToolOutput


class AddToolResult(StrictModel):
    name: Literal["add"]
    result: AddToolOutput


ToolResult = EchoToolResult | AddToolResult


class ToolDescriptor(StrictModel):
    name: str
    title: str
    description: str
    input_schema: dict
    output_schema: dict


class ListToolsResponse(StrictModel):
    tools: list[ToolDescriptor]


class HealthResponse(StrictModel):
    status: Literal["ok"]
