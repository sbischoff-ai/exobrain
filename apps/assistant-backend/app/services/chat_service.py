from __future__ import annotations

from collections.abc import AsyncIterator
import asyncio
import logging
import uuid

from app.agents.base import ChatAgent
from app.api.schemas.auth import UnifiedPrincipal
from app.services.chat_stream import ChatStreamEvent
from app.services.journal_service import JournalService

logger = logging.getLogger(__name__)

_SENTINEL = object()


class ChatService:
    """Use-case service for chat messaging and journal persistence orchestration."""

    def __init__(self, agent: ChatAgent, journal_service: JournalService) -> None:
        self._agent = agent
        self._journal_service = journal_service
        self._streams: dict[str, asyncio.Queue[ChatStreamEvent | object]] = {}

    async def start_journal_stream(
        self,
        *,
        principal: UnifiedPrincipal,
        message: str,
        client_message_id: str,
    ) -> str:
        stream_id = str(uuid.uuid4())
        queue: asyncio.Queue[ChatStreamEvent | object] = asyncio.Queue()
        self._streams[stream_id] = queue
        asyncio.create_task(
            self._produce_journal_stream(
                stream_id=stream_id,
                queue=queue,
                principal=principal,
                message=message,
                client_message_id=client_message_id,
            )
        )
        return stream_id

    async def stream_events(self, stream_id: str) -> AsyncIterator[ChatStreamEvent]:
        queue = self._streams.get(stream_id)
        if queue is None:
            yield {"type": "error", "data": {"message": "Unknown stream id"}}
            return

        while True:
            event = await queue.get()
            if event is _SENTINEL:
                self._streams.pop(stream_id, None)
                return
            yield event

    async def _produce_journal_stream(
        self,
        *,
        stream_id: str,
        queue: asyncio.Queue[ChatStreamEvent | object],
        principal: UnifiedPrincipal,
        message: str,
        client_message_id: str,
    ) -> None:
        try:
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
            async for event in self._agent.astream(message=message, conversation_id=conversation_id):
                await queue.put(event)
                if event["type"] == "message_chunk":
                    text = event["data"].get("text") if isinstance(event.get("data"), dict) else None
                    if isinstance(text, str):
                        chunks.append(text)

            assistant_message = "".join(chunks).strip()
            if assistant_message:
                await self._journal_service.create_journal_message(
                    conversation_id=conversation_id,
                    user_id=principal.user_id,
                    role="assistant",
                    content=assistant_message,
                )
        except Exception:
            logger.exception("chat stream failed", extra={"stream_id": stream_id})
            await queue.put({"type": "error", "data": {"message": "Assistant stream failed"}})
        finally:
            await queue.put(_SENTINEL)
