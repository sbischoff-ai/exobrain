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


@lru_cache
def get_chat_service() -> ChatService:
    settings = get_settings()
    logger.info("initializing chat service", extra={"use_mock_agent": settings.main_agent_use_mock})
    return ChatService(agent=build_main_agent(settings))


async def _response_stream(
    message: str,
    principal: UnifiedPrincipal,
    client_message_id: str,
    journal_service: JournalService,
) -> AsyncIterator[str]:
    reference = journal_service.today_reference()
    conversation_id = await journal_service.ensure_journal(principal.user_id, reference)
    await journal_service.create_journal_message(
        conversation_id=conversation_id,
        user_id=principal.user_id,
        role="user",
        content=message,
        client_message_id=client_message_id,
    )

    chat_service = get_chat_service()
    chunks: list[str] = []
    async for chunk in chat_service.stream_message(message):
        chunks.append(chunk)
        yield chunk

    assistant_message = "".join(chunks).strip()
    if assistant_message:
        await journal_service.create_journal_message(
            conversation_id=conversation_id,
            user_id=principal.user_id,
            role="assistant",
            content=assistant_message,
        )


@router.post("/message")
async def message(
    payload: ChatMessageRequest,
    request: Request,
    auth_context: UnifiedPrincipal = Depends(get_required_auth_context),
) -> StreamingResponse:
    logger.info("assistant chat request", extra={"user_name": auth_context.display_name})
    journal_service: JournalService = request.app.state.journal_service
    return StreamingResponse(
        _response_stream(payload.message, auth_context, str(payload.client_message_id), journal_service),
        media_type="text/plain",
    )
