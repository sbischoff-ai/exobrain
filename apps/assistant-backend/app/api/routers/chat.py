from collections.abc import AsyncIterator
from functools import lru_cache
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.agents.factory import build_main_agent
from app.api.dependencies.auth import get_required_auth_context
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.chat import ChatMessageRequest
from app.core.settings import get_settings
from app.services.chat_service import ChatService
from app.services.journal_service import JournalService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

ASSISTANT_STREAM_ERROR_FALLBACK = (
    "I ran into a temporary issue while generating a response. Please try again in a moment."
)


@lru_cache
def get_chat_service() -> ChatService:
    settings = get_settings()
    logger.info("initializing chat service", extra={"use_mock_agent": settings.main_agent_use_mock})
    return ChatService(agent=build_main_agent(settings))


async def _response_stream(
    message: str,
    principal: UnifiedPrincipal,
    conversation_id: str,
    journal_service: JournalService,
) -> AsyncIterator[str]:
    chat_service = get_chat_service()
    chunks: list[str] = []

    try:
        async for chunk in chat_service.stream_message(message):
            chunks.append(chunk)
            yield chunk
    except Exception:
        # Keep the HTTP stream well-formed even if the upstream model call fails mid-stream.
        logger.exception("assistant stream failed; sending fallback message")
        chunks = [ASSISTANT_STREAM_ERROR_FALLBACK]
        yield ASSISTANT_STREAM_ERROR_FALLBACK

    assistant_message = "".join(chunks).strip()
    if assistant_message:
        await journal_service.create_journal_message(
            conversation_id=conversation_id,
            user_id=principal.user_id,
            role="assistant",
            content=assistant_message,
        )


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
    journal_service: JournalService = request.app.state.journal_service

    # Persist write-path preconditions before opening a streaming response so schema/config
    # issues (for example missing migrations/tables) fail as normal request errors, not
    # incomplete chunked responses.
    reference = journal_service.today_reference()
    conversation_id = await journal_service.ensure_journal(auth_context.user_id, reference)
    await journal_service.create_journal_message(
        conversation_id=conversation_id,
        user_id=auth_context.user_id,
        role="user",
        content=payload.message,
        client_message_id=str(payload.client_message_id),
    )

    return StreamingResponse(
        _response_stream(payload.message, auth_context, conversation_id, journal_service),
        media_type="text/plain",
    )
