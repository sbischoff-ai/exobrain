from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import Field

from app.contracts.base import StrictModel


class ToolMetadata(StrictModel):
    name: str
    description: str
    inputSchema: dict[str, Any]


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


class ResolveEntityExpectedExistence(str, Enum):
    NEW = "new"
    EXISTING = "existing"
    UNKNOWN = "unknown"


class ResolveEntitiesInputItem(StrictModel):
    name: str = Field(min_length=1)
    type_hint: str | None = Field(default=None, max_length=120)
    description_hint: str | None = Field(default=None, max_length=300)
    expected_existence: ResolveEntityExpectedExistence = ResolveEntityExpectedExistence.UNKNOWN


class ResolveEntitiesToolInput(StrictModel):
    entities: list[ResolveEntitiesInputItem] = Field(min_length=1)


class ResolveEntityMatchStatus(str, Enum):
    MATCHED = "matched"
    CREATED = "created"
    UNRESOLVED = "unresolved"


class ResolveEntitiesOutputItem(StrictModel):
    entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    aliases: list[str]
    entity_type: str = Field(min_length=1)
    description: str
    status: ResolveEntityMatchStatus
    confidence: float = Field(ge=0.0, le=1.0)
    newly_created: bool


class ResolveEntitiesToolOutput(StrictModel):
    results: list[ResolveEntitiesOutputItem]


class ToolInvocation(StrictModel):
    name: str = Field(min_length=1)
    arguments: dict[str, Any]
    metadata: CorrelationMetadata | None = None


class ToolError(StrictModel):
    code: str
    message: str


class GenericToolSuccessEnvelope(StrictModel):
    """Fallback success envelope for dynamically registered tools."""

    ok: Literal[True] = True
    name: str
    result: Any
    metadata: CorrelationMetadata | None = None


class ToolErrorEnvelope(StrictModel):
    ok: Literal[False] = False
    name: str
    error: ToolError
    metadata: CorrelationMetadata | None = None


ToolSuccessEnvelope = GenericToolSuccessEnvelope
ToolResult = ToolSuccessEnvelope | ToolErrorEnvelope
