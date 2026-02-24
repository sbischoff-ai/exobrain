from pydantic import BaseModel, Field


class CreateKnowledgeJobRequest(BaseModel):
    operation: str = Field(..., min_length=1, description="Knowledge job operation, for example ingest or reindex")
    reference: str = Field(..., min_length=1, description="Journal or resource reference used by the worker")
    metadata: dict[str, str] = Field(default_factory=dict, description="Optional job metadata for worker logic")


class CreateKnowledgeJobResponse(BaseModel):
    job_id: str = Field(..., description="Enqueued job identifier")
    status: str = Field(default="queued", description="Initial accepted status")
