import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.dependencies.auth import get_required_auth_context
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.chat import ChatMessageRequest
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/message",
    summary="Stream assistant response and persist journal messages",
    description="Persists the user message, streams assistant output, then persists the assistant reply in the current journal entry.",
)
async def message(
    payload: ChatMessageRequest,
    request: Request,
    auth_context: UnifiedPrincipal = Depends(get_required_auth_context),
) -> StreamingResponse:
    logger.info("assistant chat request", extra={"user_name": auth_context.display_name})
    chat_service: ChatService = request.app.state.chat_service
    return StreamingResponse(
        chat_service.stream_journal_message(
            principal=auth_context,
            message=payload.message,
            client_message_id=str(payload.client_message_id),
        ),
        media_type="text/plain",
    )
