import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.dependencies.auth import get_required_auth_context
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.chat import ChatMessageRequest, ChatMessageStartResponse
from app.services.chat_service import ChatService
from app.services.chat_stream import encode_sse_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/message",
    summary="Start assistant response stream and persist journal messages",
    description=(
        "Persists the user message, starts asynchronous assistant generation, and returns a stream_id. "
        "Consume events from GET /api/chat/stream/{stream_id}."
    ),
    response_model=ChatMessageStartResponse,
)
async def message(
    payload: ChatMessageRequest,
    request: Request,
    auth_context: UnifiedPrincipal = Depends(get_required_auth_context),
) -> ChatMessageStartResponse:
    logger.info("assistant chat request", extra={"user_name": auth_context.display_name})
    chat_service: ChatService = request.app.state.chat_service
    stream_id = await chat_service.start_journal_stream(
        principal=auth_context,
        message=payload.message,
        client_message_id=str(payload.client_message_id),
    )
    return ChatMessageStartResponse(stream_id=stream_id)


@router.get(
    "/stream/{stream_id}",
    summary="Consume assistant SSE stream",
    description=(
        "Server-sent event stream for a previously started chat response. "
        "Event types currently include tool_call, tool_response, error, message_chunk, and done."
    ),
)
async def stream(
    stream_id: str,
    request: Request,
    _auth_context: UnifiedPrincipal = Depends(get_required_auth_context),
) -> StreamingResponse:
    chat_service: ChatService = request.app.state.chat_service

    async def event_stream() -> str:
        async for event in chat_service.stream_events(stream_id):
            yield encode_sse_event(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
