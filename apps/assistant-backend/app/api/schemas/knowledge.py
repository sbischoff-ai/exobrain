from pydantic import BaseModel, Field


class KnowledgeUpdateRequest(BaseModel):
    journal_reference: str = Field(..., min_length=1, description="Journal reference in YYYY/MM/DD format")


class KnowledgeUpdateResponse(BaseModel):
    job_id: str = Field(..., description="Enqueued knowledge update job identifier")
    status: str = Field(default="queued", description="Initial accepted status")
