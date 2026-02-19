from __future__ import annotations

from datetime import UTC, datetime

from app.services.conversation_service import ConversationService


class JournalService:
    """Journal-focused orchestration over the generic conversation service."""

    def __init__(self, conversation_service: ConversationService) -> None:
        self._conversation_service = conversation_service

    async def ensure_journal(self, user_id: str, reference: str) -> str:
        return await self._conversation_service.ensure_conversation(user_id=user_id, reference=reference)

    async def create_journal_message(
        self,
        *,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        client_message_id: str | None = None,
    ) -> str:
        return await self._conversation_service.insert_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role=role,
            content=content,
            client_message_id=client_message_id,
        )

    async def list_journals(self, user_id: str, limit: int, before: str | None = None):
        return await self._conversation_service.list_conversations(user_id=user_id, limit=limit, before=before)

    async def get_journal(self, user_id: str, reference: str):
        return await self._conversation_service.get_conversation_by_reference(user_id=user_id, reference=reference)

    async def get_today_journal(self, user_id: str, create: bool = False):
        reference = self.today_reference()
        if create:
            await self.ensure_journal(user_id=user_id, reference=reference)
        return await self.get_journal(user_id=user_id, reference=reference)

    async def list_messages(self, user_id: str, reference: str, limit: int):
        return await self._conversation_service.list_messages(user_id=user_id, reference=reference, limit=limit)

    async def list_today_messages(self, user_id: str, limit: int):
        return await self.list_messages(user_id=user_id, reference=self.today_reference(), limit=limit)

    async def search_journals(self, user_id: str, query: str, limit: int):
        return await self._conversation_service.search_conversations(user_id=user_id, query=query, limit=limit)

    @staticmethod
    def today_reference() -> str:
        return datetime.now(UTC).strftime("%Y/%m/%d")
