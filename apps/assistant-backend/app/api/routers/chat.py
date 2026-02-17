from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agents.factory import build_main_agent
from app.api.dependencies.auth import get_optional_auth_context
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.chat import ChatMessageRequest
from app.core.settings import get_settings
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@lru_cache
def get_chat_service() -> ChatService:
    settings = get_settings()
    return ChatService(agent=build_main_agent(settings))


async def _response_stream(message: str) -> AsyncIterator[str]:
    chat_service = get_chat_service()
    async for chunk in chat_service.stream_message(message):
        yield chunk


@router.post("/message")
async def message(
    payload: ChatMessageRequest,
    auth_context: UnifiedPrincipal | None = Depends(get_optional_auth_context),
) -> StreamingResponse:
    user_name = auth_context.display_name if auth_context is not None else "anonymous"
    print(f"assistant chat request by user={user_name}")
    return StreamingResponse(_response_stream(payload.message), media_type="text/plain")
