from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


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


class KnowledgeCategoryPageMetadata(BaseModel):
    created_at: str = Field(
        default="",
        description="Upstream entity creation timestamp from ListEntitiesByType when available",
    )
    updated_at: str = Field(
        default="",
        description="Upstream entity update timestamp from ListEntitiesByType when available",
    )


class KnowledgeCategoryPageListItem(BaseModel):
    id: str = Field(
        ...,
        description="Page identifier",
    )
    title: str = Field(
        ...,
        description="Page title",
    )
    summary: str | None = Field(
        default=None,
        description="Page summary",
    )
    metadata: KnowledgeCategoryPageMetadata = Field(
        default_factory=KnowledgeCategoryPageMetadata,
        description="Page metadata including created and updated timestamps",
    )


class KnowledgeCategoryPagesListResponse(BaseModel):
    knowledge_pages: list[KnowledgeCategoryPageListItem] = Field(
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


class KnowledgePageContentBlock(BaseModel):
    block_id: str = Field(..., description="Stable identifier for one entity content block")
    markdown: str = Field(
        ...,
        description="Markdown for this single entity block; clients render each block independently",
    )


class KnowledgePageDetailResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(
        ...,
        description="Mapped page identifier",
    )
    category_id: str = Field(
        ...,
        description="Node type identifier for the page entity category",
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
    properties: dict[str, str] = Field(
        default_factory=dict,
        description="Entity-type-specific key/value properties from the upstream entity context",
    )
    links: list[dict[str, str | None]] = Field(
        default_factory=list,
        description="Mapped related pages from entity neighbors, deduplicated by page_id",
    )
    content_blocks: list[KnowledgePageContentBlock] = Field(
        default_factory=list,
        description="Ordered entity content blocks, where each item is rendered independently by clients",
    )
