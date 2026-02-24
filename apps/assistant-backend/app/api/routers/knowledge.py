from fastapi import APIRouter, Depends, Request

from app.api.dependencies.auth import get_required_auth_context
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.knowledge import KnowledgeUpdateRequest, KnowledgeUpdateResponse
from app.dependency_injection import get_container
from app.services.contracts import KnowledgeServiceProtocol

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post(
    "/update",
    response_model=KnowledgeUpdateResponse,
    summary="Queue knowledge graph update job",
    description="Enqueue a knowledge.update job using all messages from a journal reference.",
)
async def enqueue_knowledge_update(
    payload: KnowledgeUpdateRequest,
    request: Request,
    auth_context: UnifiedPrincipal = Depends(get_required_auth_context),
) -> KnowledgeUpdateResponse:
    service = get_container(request).resolve(KnowledgeServiceProtocol)
    job_id = await service.enqueue_update_job(
        user_id=auth_context.user_id,
        journal_reference=payload.journal_reference,
    )
    return KnowledgeUpdateResponse(job_id=job_id)
