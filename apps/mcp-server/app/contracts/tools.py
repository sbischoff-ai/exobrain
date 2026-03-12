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
    query: str = Field(
        min_length=1,
        description="Search phrase describing what information to find on the web.",
        examples=["latest qdrant release notes"],
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of ranked results to return; use smaller values for focused lookups.",
        examples=[5],
    )
    recency_days: int | None = Field(
        default=None,
        ge=1,
        description="Optional freshness window in days; set to bias results toward recently published pages.",
        examples=[30],
    )
    include_domains: list[str] | None = Field(
        default=None,
        description="Optional domain allowlist (hostnames only) to restrict search results.",
        examples=[["docs.python.org", "fastapi.tiangolo.com"]],
    )
    exclude_domains: list[str] | None = Field(
        default=None,
        description="Optional domain blocklist (hostnames only) to filter out unwanted sources.",
        examples=[["pinterest.com", "facebook.com"]],
    )


class WebSearchResultItem(StrictModel):
    title: str
    url: str
    snippet: str
    score: float | None = None
    published_at: str | None = None


class WebSearchToolOutput(StrictModel):
    results: list[WebSearchResultItem]


class WebFetchToolInput(StrictModel):
    url: str = Field(
        min_length=1,
        description="Absolute HTTP(S) URL of the page to fetch and extract readable text from.",
        examples=["https://example.com/blog/ai-updates"],
    )
    max_chars: int = Field(
        default=4000,
        ge=100,
        le=20000,
        description="Maximum number of characters to return from extracted content; increase for long-form pages.",
        examples=[4000],
    )


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
    name: str = Field(
        min_length=1,
        description="Primary entity name exactly as mentioned in user context.",
        examples=["OpenAI"],
    )
    type_hint: str | None = Field(
        default=None,
        max_length=120,
        description="Optional short category hint (for example person, company, product) to improve matching.",
        examples=["company"],
    )
    description_hint: str | None = Field(
        default=None,
        max_length=300,
        description="Optional disambiguation details such as role, location, or timeframe.",
        examples=["AI research organization based in San Francisco"],
    )
    expected_existence: ResolveEntityExpectedExistence = Field(
        default=ResolveEntityExpectedExistence.UNKNOWN,
        description="Whether this entity is expected to already exist in memory: new, existing, or unknown.",
        examples=["existing"],
    )


class ResolveEntitiesToolInput(StrictModel):
    entities: list[ResolveEntitiesInputItem] = Field(
        min_length=1,
        description="One or more entities to resolve, each with a name and optional disambiguation hints.",
        examples=[[{"name": "Alice Johnson", "type_hint": "person", "expected_existence": "unknown"}]],
    )


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


class GetEntityContextToolInput(StrictModel):
    entity_id: str = Field(
        min_length=1,
        description="Canonical entity identifier from resolve_entities used as the context lookup root.",
        examples=["ent_openai"],
    )
    depth: int | None = Field(
        default=None,
        ge=0,
        le=32,
        description="Optional traversal depth bound for related evidence blocks; maps to knowledge max_block_level.",
        examples=[5],
    )
    focus: str | None = Field(
        default=None,
        max_length=160,
        description="Optional short focus prompt to guide LLM-based context condensing toward the current user intent.",
        examples=["Open-source model releases and enterprise partnerships"],
    )


class GetEntityContextRelatedEntityItem(StrictModel):
    entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    aliases: list[str]
    entity_type: str = Field(min_length=1)
    description: str


class GetEntityContextToolOutput(StrictModel):
    context_markdown: str = Field(
        description="Agent-ready markdown summary for the requested entity, including salient context extracted from memory.",
        examples=["# OpenAI\n\nOpenAI is an AI research and deployment company..."],
    )
    related_entities: list[GetEntityContextRelatedEntityItem] = Field(
        description="Nearby entities connected to the requested entity and suitable for follow-up get_entity_context calls.",
    )


class ToolInvocation(StrictModel):
    name: str = Field(min_length=1)
    arguments: dict[str, Any]
    metadata: CorrelationMetadata | None = None


class ToolExecutionContext(StrictModel):
    user_id: str = Field(min_length=1)
    name: str = Field(min_length=1)


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
