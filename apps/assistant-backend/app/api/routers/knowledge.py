from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.api.dependencies.auth import get_required_auth_context
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.knowledge import (
    KnowledgeCategoryTreeResponse,
    KnowledgeCategoryPagesListResponse,
    KnowledgePageDetailResponse,
    KnowledgeUpdateRequest,
    KnowledgeUpdateResponse,
)
from app.dependency_injection import get_container
from app.services.contracts import KnowledgeServiceProtocol
from app.services.knowledge_interface_client import (
    KnowledgeInterfaceClientError,
    KnowledgeInterfaceClientInvalidArgumentError,
    KnowledgeInterfaceClientUnavailableError,
)
from app.services.knowledge_service import (
    KnowledgeEnqueueError,
    KnowledgeJobAccessDeniedError,
    KnowledgeJobNotFoundError,
    KnowledgeNoPendingMessagesError,
    KnowledgePageAccessDeniedError,
    KnowledgePageNotFoundError,
    KnowledgePageUnavailableError,
    KnowledgePageUpstreamError,
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
    responses={
        409: {
            "description": "No uncommitted messages were found for the requested scope"
        },
        503: {
            "description": "Job orchestrator unavailable while attempting to enqueue"
        },
        502: {"description": "Unexpected enqueue error from job orchestrator"},
    },
)
async def enqueue_knowledge_update(
    payload: KnowledgeUpdateRequest,
    request: Request,
    auth_context: UnifiedPrincipal = Depends(get_required_auth_context),
) -> KnowledgeUpdateResponse:
    service = get_container(request).resolve(KnowledgeServiceProtocol)
    try:
        job_id = await service.enqueue_update_job(
            user_id=auth_context.user_id,
            journal_reference=payload.journal_reference,
        )
    except KnowledgeNoPendingMessagesError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="no uncommitted messages available for knowledge update",
        ) from exc
    except KnowledgeUpstreamUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="knowledge update enqueue unavailable",
        ) from exc
    except KnowledgeEnqueueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="knowledge update enqueue failed",
        ) from exc

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
    stream = service.watch_update_job(user_id=auth_context.user_id, job_id=job_id)

    first_event: dict[str, object] | None = None
    try:
        first_event = await anext(stream)
    except StopAsyncIteration:
        first_event = None
    except KnowledgeJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="knowledge update job not found",
        ) from exc
    except KnowledgeJobAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="knowledge update job access denied",
        ) from exc
    except KnowledgeUpstreamUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="knowledge stream unavailable",
        ) from exc
    except KnowledgeWatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="knowledge stream error"
        ) from exc

    async def event_stream() -> str:
        if first_event is not None:
            yield encode_knowledge_sse_event(first_event)

        async for event in stream:
            yield encode_knowledge_sse_event(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get(
    "/category",
    response_model=KnowledgeCategoryTreeResponse,
    summary="List the knowledge category tree",
    description="Returns active wiki categories rooted at direct node.entity subtypes (excluding node.block/node.universe), then nested by subtype inheritance.",
    responses={
        400: {"description": "Invalid knowledge category request"},
        503: {"description": "knowledge-interface unavailable or timed out"},
        502: {"description": "Unexpected upstream failure from knowledge-interface"},
    },
)
async def list_knowledge_categories(
    request: Request,
    _auth_context: UnifiedPrincipal = Depends(get_required_auth_context),
) -> KnowledgeCategoryTreeResponse:
    service = get_container(request).resolve(KnowledgeServiceProtocol)

    try:
        categories = await service.list_wiki_category_tree(universe_id="wiki")
    except KnowledgeInterfaceClientInvalidArgumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid knowledge categories request",
        ) from exc
    except KnowledgeInterfaceClientUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="knowledge categories unavailable",
        ) from exc
    except KnowledgeInterfaceClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="knowledge categories upstream failure",
        ) from exc

    return KnowledgeCategoryTreeResponse(categories=categories)


@router.get(
    "/category/{category_id}/pages",
    response_model=KnowledgeCategoryPagesListResponse,
    summary="List pages for a knowledge category",
    description="Returns page summaries for a category using knowledge-interface ListEntitiesByType pagination.",
    responses={
        400: {"description": "Invalid pagination or category arguments"},
        503: {"description": "knowledge-interface unavailable or timed out"},
        502: {"description": "Unexpected upstream failure from knowledge-interface"},
    },
)
async def list_knowledge_category_pages(
    category_id: str,
    request: Request,
    auth_context: UnifiedPrincipal = Depends(get_required_auth_context),
    page_size: Annotated[
        int | None, Query(ge=1, description="Maximum pages to return")
    ] = None,
    page_token: Annotated[
        str | None, Query(min_length=1, description="Opaque continuation token")
    ] = None,
) -> KnowledgeCategoryPagesListResponse:
    service = get_container(request).resolve(KnowledgeServiceProtocol)

    try:
        payload = await service.list_category_pages(
            user_id=auth_context.user_id,
            category_id=category_id,
            page_size=page_size,
            page_token=page_token,
        )
    except KnowledgeInterfaceClientInvalidArgumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid knowledge category pages request",
        ) from exc
    except KnowledgeInterfaceClientUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="knowledge category pages unavailable",
        ) from exc
    except KnowledgeInterfaceClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="knowledge category pages upstream failure",
        ) from exc

    return KnowledgeCategoryPagesListResponse.model_validate(payload)


@router.get(
    "/page/{page_id}",
    response_model=KnowledgePageDetailResponse,
    summary="Get knowledge page details",
    description="Returns full page detail by page id using knowledge-interface GetEntityContext.",
    responses={
        403: {"description": "Requested page is inaccessible for the caller"},
        404: {"description": "Requested page does not exist"},
        503: {"description": "knowledge-interface unavailable or timed out"},
        502: {"description": "Unexpected upstream failure from knowledge-interface"},
    },
)
async def get_knowledge_page(
    page_id: str,
    request: Request,
    auth_context: UnifiedPrincipal = Depends(get_required_auth_context),
) -> KnowledgePageDetailResponse:
    service = get_container(request).resolve(KnowledgeServiceProtocol)

    try:
        payload = await service.get_page_detail(
            user_id=auth_context.user_id, page_id=page_id
        )
    except KnowledgePageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="knowledge page not found"
        ) from exc
    except KnowledgePageAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="knowledge page access denied"
        ) from exc
    except KnowledgePageUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="knowledge page unavailable",
        ) from exc
    except KnowledgePageUpstreamError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="knowledge page upstream failure",
        ) from exc

    return KnowledgePageDetailResponse.model_validate(payload)
