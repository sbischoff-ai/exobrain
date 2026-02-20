from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import asyncpg

from app.services.conversation_service import ConversationService


class JournalService:
    """Service that projects conversation operations into journal-specific workflows."""

    def __init__(self, conversation_service: ConversationService) -> None:
        self._conversation_service = conversation_service

    async def ensure_journal(self, user_id: str, journal_reference: str) -> str:
        """Ensure a journal conversation exists for a reference and return its id."""
        return await self._conversation_service.ensure_conversation(user_id=user_id, reference=journal_reference)

    async def create_journal_message(
        self,
        *,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        client_message_id: str | None = None,
    ) -> str:
        """Persist a journal message in an existing conversation."""
        return await self._conversation_service.insert_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role=role,
            content=content,
            client_message_id=client_message_id,
        )

    async def list_journals(self, user_id: str, limit: int, before: str | None = None) -> Sequence[asyncpg.Record]:
        """List journal entries using reference-based cursor pagination."""
        return await self._conversation_service.list_conversations(user_id=user_id, limit=limit, before=before)

    async def get_journal(self, user_id: str, journal_reference: str) -> asyncpg.Record | None:
        """Load one journal entry by exact reference."""
        return await self._conversation_service.get_conversation_by_reference(
            user_id=user_id,
            reference=journal_reference,
        )

    async def get_today_journal(self, user_id: str, create: bool = False) -> asyncpg.Record | None:
        """Get today's journal entry, optionally creating it if absent."""
        journal_reference = self.today_reference()
        if create:
            await self.ensure_journal(user_id=user_id, journal_reference=journal_reference)
        return await self.get_journal(user_id=user_id, journal_reference=journal_reference)

    async def list_messages(
        self,
        user_id: str,
        journal_reference: str,
        limit: int,
        before_sequence: int | None = None,
    ) -> Sequence[asyncpg.Record]:
        """List journal messages ordered by descending sequence with optional cursor."""
        return await self._conversation_service.list_messages(
            user_id=user_id,
            conversation_reference=journal_reference,
            limit=limit,
            before_sequence=before_sequence,
        )

    async def list_today_messages(self, user_id: str, limit: int, before_sequence: int | None = None) -> Sequence[asyncpg.Record]:
        """List messages for today's journal reference."""
        return await self.list_messages(
            user_id=user_id,
            journal_reference=self.today_reference(),
            limit=limit,
            before_sequence=before_sequence,
        )

    async def search_journals(self, user_id: str, query: str, limit: int) -> Sequence[asyncpg.Record]:
        """Search journals by reference and message content."""
        return await self._conversation_service.search_conversations(user_id=user_id, query=query, limit=limit)

    @staticmethod
    def today_reference() -> str:
        """Format the current UTC date as a journal reference."""
        return datetime.now(UTC).strftime("%Y/%m/%d")
