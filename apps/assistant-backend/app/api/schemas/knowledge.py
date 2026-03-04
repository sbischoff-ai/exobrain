from __future__ import annotations

from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field


class KnowledgeUpdateRequest(BaseModel):
    journal_reference: str | None = Field(
        default=None,
        min_length=1,
        description="Optional journal reference in YYYY/MM/DD format; when omitted, enqueues all uncommitted messages",
    )


class KnowledgeUpdateResponse(BaseModel):
    job_id: str = Field(
        ...,
        description="Identifier of the first accepted knowledge-base update request",
    )
    status: str = Field(default="queued", description="Initial accepted status")


class KnowledgeCategoryTreeItem(BaseModel):
    category_id: str = Field(
        ..., description="Stable identifier for the knowledge category"
    )
    display_name: str = Field(..., description="Human-friendly category name")
    sub_categories: list[KnowledgeCategoryTreeItem] = Field(
        default_factory=list,
        description="Nested child categories for this node in the tree",
    )


class KnowledgeCategoryTreeResponse(BaseModel):
    categories: list[KnowledgeCategoryTreeItem] = Field(
        default_factory=list,
        description="Top-level category tree nodes available to the user",
    )


class KnowledgePageEntitySummary(BaseModel):
    id: str = Field(
        ..., description="Upstream entity identifier from ListEntitiesByType"
    )
    name: str = Field(..., description="Upstream entity name from ListEntitiesByType")
    description: str | None = Field(
        default=None,
        description="Upstream entity description from ListEntitiesByType when available",
    )
    updated_at: str | None = Field(
        default=None,
        description="Upstream entity update timestamp from ListEntitiesByType when available",
    )
    score: float | None = Field(
        default=None,
        description="Upstream relevance score from ListEntitiesByType when available",
    )


class KnowledgeCategoryPageListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    entity: KnowledgePageEntitySummary = Field(
        ...,
        description="Original entity payload returned by ListEntitiesByType",
    )
    page_id: str = Field(
        ...,
        validation_alias=AliasChoices("page_id", AliasPath("entity", "id")),
        description="Mapped page identifier (alias of entity.id)",
    )
    page_title: str = Field(
        ...,
        validation_alias=AliasChoices("page_title", AliasPath("entity", "name")),
        description="Mapped page title (alias of entity.name)",
    )
    page_summary: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "page_summary", AliasPath("entity", "description")
        ),
        description="Mapped page summary (alias of entity.description)",
    )


class KnowledgeCategoryPagesListResponse(BaseModel):
    pages: list[KnowledgeCategoryPageListItem] = Field(
        default_factory=list,
        description="Page summaries within the selected category",
    )
    page_size: int = Field(..., ge=1, description="Requested number of items per page")
    next_page_token: str | None = Field(
        default=None,
        description="Pagination cursor for the next result page, when more items are available",
    )
    total_count: int | None = Field(
        default=None,
        ge=0,
        description="Total number of matching pages when provided by the upstream service",
    )


class KnowledgePageMetadata(BaseModel):
    created_at: str = Field(..., description="Upstream entity creation timestamp")
    updated_at: str = Field(..., description="Upstream entity last-update timestamp")


class KnowledgePageDetailResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    page_id: str = Field(
        ...,
        description="Mapped page identifier",
    )
    title: str = Field(
        ...,
        validation_alias=AliasChoices("title"),
        description="Page title for rendering in the knowledge UI",
    )
    summary: str | None = Field(
        default=None,
        validation_alias=AliasChoices("summary"),
        description="Optional page summary for previews and metadata",
    )
    metadata: KnowledgePageMetadata = Field(
        ...,
        validation_alias=AliasChoices("metadata"),
        description="Page metadata including canonical timestamps only",
    )
    links: list[dict[str, str | None]] = Field(
        default_factory=list,
        description="Mapped related pages from entity neighbors",
    )
    content_markdown: str = Field(
        ...,
        validation_alias=AliasChoices("content_markdown", "prompt_context_markdown"),
        description="Full markdown content to render for the page detail view",
    )
