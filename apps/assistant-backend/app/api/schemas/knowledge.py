from pydantic import BaseModel, Field


class KnowledgeUpdateRequest(BaseModel):
    journal_reference: str | None = Field(
        default=None,
        min_length=1,
        description="Optional journal reference in YYYY/MM/DD format; when omitted, enqueues all uncommitted messages",
    )


class KnowledgeUpdateResponse(BaseModel):
    job_id: str = Field(..., description="Identifier of the first accepted knowledge-base update request")
    status: str = Field(default="queued", description="Initial accepted status")
