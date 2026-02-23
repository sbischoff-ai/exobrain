from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import logging
from typing import Any

import asyncpg

from app.core.settings import Settings
from app.services.contracts import ConversationServiceProtocol, JournalCacheProtocol

logger = logging.getLogger(__name__)

_NEGATIVE_CACHE_MARKER = "__not_found__"


class JournalService:
    """Service that projects conversation operations into journal-specific workflows."""

    def __init__(
        self,
        conversation_service: ConversationServiceProtocol,
        cache: JournalCacheProtocol,
        settings: Settings,
    ) -> None:
        self._conversation_service = conversation_service
        self._cache = cache
        self._settings = settings

    async def ensure_journal(self, user_id: str, journal_reference: str) -> str:
        """Ensure a journal conversation exists for a reference and return its id."""
        conversation_id = await self._conversation_service.ensure_conversation(user_id=user_id, reference=journal_reference)
        await self._invalidate_for_reference(user_id=user_id, reference=journal_reference)
        return conversation_id

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
        message_id = await self._conversation_service.insert_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role=role,
            content=content,
            client_message_id=client_message_id,
        )
        reference = await self._conversation_service.get_reference_by_conversation_id(conversation_id, user_id)
        if reference is not None:
            await self._invalidate_for_reference(user_id=user_id, reference=reference)
        return message_id

    async def list_journals(self, user_id: str, limit: int, before: str | None = None) -> Sequence[Mapping[str, Any]]:
        """List journal entries using reference-based cursor pagination."""
        cache_key = self._key_journals(user_id=user_id, limit=limit, before=before)
        index_key = self._index_user_lists(user_id)

        cached = await self._cache.get_json(cache_key)
        if isinstance(cached, list):
            logger.debug("journal cache hit", extra={"cache_area": "journal_list"})
            return cached

        rows = await self._conversation_service.list_conversations(user_id=user_id, limit=limit, before=before)
        payload = [self._entry_payload(row) for row in rows]
        await self._cache.set_json(cache_key, payload, ttl_seconds=self._settings.assistant_journal_cache_list_ttl_seconds)
        await self._cache.index_key(index_key, cache_key)
        return payload

    async def get_journal(self, user_id: str, journal_reference: str) -> Mapping[str, Any] | None:
        """Load one journal entry by exact reference."""
        cache_key = self._key_journal_entry(user_id=user_id, journal_reference=journal_reference)
        cached = await self._cache.get_json(cache_key)
        if cached == _NEGATIVE_CACHE_MARKER:
            return None
        if isinstance(cached, dict):
            logger.debug("journal cache hit", extra={"cache_area": "journal_entry"})
            return cached

        row = await self._conversation_service.get_conversation_by_reference(
            user_id=user_id,
            reference=journal_reference,
        )
        if row is None:
            await self._cache.set_json(
                cache_key,
                _NEGATIVE_CACHE_MARKER,
                ttl_seconds=self._settings.assistant_journal_cache_negative_ttl_seconds,
            )
            return None

        payload = self._entry_payload(row)
        await self._cache.set_json(cache_key, payload, ttl_seconds=self._settings.assistant_journal_cache_entry_ttl_seconds)
        await self._cache.index_key(self._index_reference(user_id=user_id, journal_reference=journal_reference), cache_key)
        return payload

    async def get_today_journal(self, user_id: str, create: bool = False) -> Mapping[str, Any] | None:
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
    ) -> Sequence[Mapping[str, Any]]:
        """List journal messages ordered by descending sequence with optional cursor."""
        cache_key = self._key_messages(
            user_id=user_id,
            journal_reference=journal_reference,
            limit=limit,
            before_sequence=before_sequence,
        )
        ref_index = self._index_reference(user_id=user_id, journal_reference=journal_reference)

        cached = await self._cache.get_json(cache_key)
        if isinstance(cached, list):
            logger.debug("journal cache hit", extra={"cache_area": "journal_messages"})
            return cached

        rows = await self._conversation_service.list_messages(
            user_id=user_id,
            conversation_reference=journal_reference,
            limit=limit,
            before_sequence=before_sequence,
        )
        payload = [self._message_payload(row) for row in rows]
        await self._cache.set_json(cache_key, payload, ttl_seconds=self._settings.assistant_journal_cache_messages_ttl_seconds)
        await self._cache.index_key(ref_index, cache_key)
        return payload

    async def list_today_messages(self, user_id: str, limit: int, before_sequence: int | None = None) -> Sequence[Mapping[str, Any]]:
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

    async def _invalidate_for_reference(self, *, user_id: str, reference: str) -> None:
        try:
            await self._cache.delete(self._key_journal_entry(user_id=user_id, journal_reference=reference))
            await self._cache.delete_indexed(self._index_reference(user_id=user_id, journal_reference=reference))
            await self._cache.delete_indexed(self._index_user_lists(user_id))
        except Exception:
            logger.exception(
                "journal cache invalidation failed",
                extra={"user_id": user_id, "reference": reference},
            )

    @staticmethod
    def _entry_payload(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "reference": row["reference"],
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "last_message_at": row.get("last_message_at"),
            "message_count": row.get("message_count", 0),
            "status": row.get("status", "open"),
        }

    @staticmethod
    def _message_payload(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "sequence": row["sequence"],
            "created_at": row.get("created_at"),
            "metadata": row.get("metadata"),
        }

    @staticmethod
    def _normalize_cursor(value: str | int | None) -> str:
        return "_" if value is None else str(value)

    def _key_journals(self, *, user_id: str, limit: int, before: str | None) -> str:
        return f"user:{user_id}:journal:list:limit:{limit}:cursor:{self._normalize_cursor(before)}"

    def _key_journal_entry(self, *, user_id: str, journal_reference: str) -> str:
        return f"user:{user_id}:journal:entry:reference:{journal_reference}"

    def _key_messages(self, *, user_id: str, journal_reference: str, limit: int, before_sequence: int | None) -> str:
        return (
            f"user:{user_id}:journal:messages:reference:{journal_reference}:"
            f"limit:{limit}:cursor:{self._normalize_cursor(before_sequence)}"
        )

    def _index_reference(self, *, user_id: str, journal_reference: str) -> str:
        return f"user:{user_id}:journal:index:reference:{journal_reference}"

    def _index_user_lists(self, user_id: str) -> str:
        return f"user:{user_id}:journal:index:lists"
