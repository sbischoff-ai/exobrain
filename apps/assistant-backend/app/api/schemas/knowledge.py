from pydantic import BaseModel, Field


class KnowledgeUpdateRequest(BaseModel):
    journal_reference: str = Field(..., min_length=1, description="Journal reference in YYYY/MM/DD format used as update source")


class KnowledgeUpdateResponse(BaseModel):
    job_id: str = Field(..., description="Identifier of the accepted knowledge-base update request")
    status: str = Field(default="queued", description="Initial accepted status")
