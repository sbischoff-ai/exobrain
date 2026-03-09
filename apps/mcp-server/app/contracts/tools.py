from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from app.contracts.base import StrictModel


class ToolMetadata(StrictModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class ListToolsResponse(StrictModel):
    tools: list[ToolMetadata]


class CorrelationMetadata(StrictModel):
    correlation_id: str | None = None
    request_id: str | None = None


class EchoToolInput(StrictModel):
    text: str = Field(min_length=1)


class EchoToolOutput(StrictModel):
    text: str


class AddToolInput(StrictModel):
    a: int
    b: int


class AddToolOutput(StrictModel):
    sum: int


class WebSearchToolInput(StrictModel):
    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=10)
    recency_days: int | None = Field(default=None, ge=1)
    include_domains: list[str] | None = None
    exclude_domains: list[str] | None = None


class WebSearchResultItem(StrictModel):
    title: str
    url: str
    snippet: str
    score: float | None = None
    published_at: str | None = None


class WebSearchToolOutput(StrictModel):
    results: list[WebSearchResultItem]


class WebFetchToolInput(StrictModel):
    url: str = Field(min_length=1)
    max_chars: int = Field(default=4000, ge=100, le=20000)


class WebFetchToolOutput(StrictModel):
    url: str
    title: str | None = None
    content_text: str
    extracted_at: str | None = None
    content_truncated: bool


class EchoToolInvocation(StrictModel):
    name: Literal["echo"]
    arguments: EchoToolInput
    metadata: CorrelationMetadata | None = None


class AddToolInvocation(StrictModel):
    name: Literal["add"]
    arguments: AddToolInput
    metadata: CorrelationMetadata | None = None


class WebSearchToolInvocation(StrictModel):
    name: Literal["web_search"]
    arguments: WebSearchToolInput
    metadata: CorrelationMetadata | None = None


class WebFetchToolInvocation(StrictModel):
    name: Literal["web_fetch"]
    arguments: WebFetchToolInput
    metadata: CorrelationMetadata | None = None


ToolInvocation = Annotated[
    EchoToolInvocation | AddToolInvocation | WebSearchToolInvocation | WebFetchToolInvocation,
    Field(discriminator="name"),
]


class ToolError(StrictModel):
    code: str
    message: str


class EchoToolSuccess(StrictModel):
    ok: Literal[True] = True
    name: Literal["echo"]
    result: EchoToolOutput
    metadata: CorrelationMetadata | None = None


class AddToolSuccess(StrictModel):
    ok: Literal[True] = True
    name: Literal["add"]
    result: AddToolOutput
    metadata: CorrelationMetadata | None = None


class WebSearchToolSuccess(StrictModel):
    ok: Literal[True] = True
    name: Literal["web_search"]
    result: WebSearchToolOutput
    metadata: CorrelationMetadata | None = None


class WebFetchToolSuccess(StrictModel):
    ok: Literal[True] = True
    name: Literal["web_fetch"]
    result: WebFetchToolOutput
    metadata: CorrelationMetadata | None = None


class ToolErrorEnvelope(StrictModel):
    ok: Literal[False] = False
    name: str
    error: ToolError
    metadata: CorrelationMetadata | None = None


ToolResult = EchoToolSuccess | AddToolSuccess | WebSearchToolSuccess | WebFetchToolSuccess | ToolErrorEnvelope
