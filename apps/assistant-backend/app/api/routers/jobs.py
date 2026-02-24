from fastapi import APIRouter, Depends, Request

from app.api.dependencies.auth import get_required_auth_context
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.jobs import CreateKnowledgeJobRequest, CreateKnowledgeJobResponse
from app.dependency_injection import get_container
from app.services.contracts import JobPublisherProtocol

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "/knowledge",
    summary="Queue asynchronous knowledge job",
    description="Queues a knowledge job on NATS and returns a queued job id for asynchronous processing.",
    response_model=CreateKnowledgeJobResponse,
)
async def enqueue_knowledge_job(
    payload: CreateKnowledgeJobRequest,
    request: Request,
    auth_context: UnifiedPrincipal = Depends(get_required_auth_context),
) -> CreateKnowledgeJobResponse:
    publisher = get_container(request).resolve(JobPublisherProtocol)
    job_type = f"knowledge.{payload.operation}"
    job_id = await publisher.enqueue_job(
        job_type=job_type,
        correlation_id=auth_context.user_id,
        payload={
            "reference": payload.reference,
            "metadata": payload.metadata,
            "requested_by_user_id": auth_context.user_id,
        },
    )
    return CreateKnowledgeJobResponse(job_id=job_id)
