from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.dependencies.auth import get_required_auth_context
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.knowledge import KnowledgeUpdateRequest, KnowledgeUpdateResponse
from app.dependency_injection import get_container
from app.services.contracts import KnowledgeServiceProtocol
from app.services.knowledge_service import (
    KnowledgeJobAccessDeniedError,
    KnowledgeJobNotFoundError,
    KnowledgeUpstreamUnavailableError,
    KnowledgeWatchError,
)
from app.services.knowledge_stream import encode_knowledge_sse_event

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post(
    "/update",
    response_model=KnowledgeUpdateResponse,
    summary="Update the knowledge base using uncommitted messages",
    description="Starts one or more knowledge-base update jobs from uncommitted journal messages, optionally scoped to a journal reference.",
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


@router.get(
    "/update/{job_id}/watch",
    summary="Watch knowledge update job status as SSE",
    description=(
        "Streams knowledge-update lifecycle events as Server-Sent Events. "
        "`event: status` carries `{job_id, state, attempt, detail, terminal, emitted_at}` for each orchestrator update. "
        "When a terminal update is reached, the stream emits `event: done` with `{job_id, state, terminal}` and closes."
    ),
)
async def watch_knowledge_update(
    job_id: str,
    request: Request,
    auth_context: UnifiedPrincipal = Depends(get_required_auth_context),
) -> StreamingResponse:
    service = get_container(request).resolve(KnowledgeServiceProtocol)

    async def event_stream() -> str:
        try:
            async for event in service.watch_update_job(user_id=auth_context.user_id, job_id=job_id):
                yield encode_knowledge_sse_event(event)
        except KnowledgeJobNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="knowledge update job not found") from exc
        except KnowledgeJobAccessDeniedError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="knowledge update job access denied") from exc
        except KnowledgeUpstreamUnavailableError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="knowledge stream unavailable") from exc
        except KnowledgeWatchError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="knowledge stream error") from exc

    return StreamingResponse(event_stream(), media_type="text/event-stream")
