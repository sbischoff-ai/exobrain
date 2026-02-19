from collections.abc import AsyncIterator
import logging

from app.agents.base import ChatAgent
from app.api.schemas.auth import UnifiedPrincipal
from app.services.journal_service import JournalService

logger = logging.getLogger(__name__)


class ChatService:
    """Use-case service for chat messaging and journal persistence orchestration."""

    def __init__(self, agent: ChatAgent, journal_service: JournalService) -> None:
        self._agent = agent
        self._journal_service = journal_service

    async def stream_message(self, message: str) -> AsyncIterator[str]:
        logger.debug("streaming chat message", extra={"message_length": len(message)})
        async for chunk in self._agent.stream(message):
            yield chunk

    async def stream_journal_message(
        self,
        *,
        principal: UnifiedPrincipal,
        message: str,
        client_message_id: str,
    ) -> AsyncIterator[str]:
        """Persist user/assistant journal messages around a streamed model response."""

        reference = self._journal_service.today_reference()
        conversation_id = await self._journal_service.ensure_journal(principal.user_id, reference)
        await self._journal_service.create_journal_message(
            conversation_id=conversation_id,
            user_id=principal.user_id,
            role="user",
            content=message,
            client_message_id=client_message_id,
        )

        chunks: list[str] = []
        async for chunk in self.stream_message(message):
            chunks.append(chunk)
            yield chunk

        assistant_message = "".join(chunks).strip()
        if assistant_message:
            await self._journal_service.create_journal_message(
                conversation_id=conversation_id,
                user_id=principal.user_id,
                role="assistant",
                content=assistant_message,
            )
