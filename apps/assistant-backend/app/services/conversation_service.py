from __future__ import annotations

from collections.abc import Sequence
import uuid

import asyncpg

from app.services.contracts import DatabaseServiceProtocol


class ConversationService:
    """Application service for conversation and message persistence."""

    def __init__(self, database: DatabaseServiceProtocol) -> None:
        self._database = database

    async def ensure_conversation(self, user_id: str, reference: str) -> str:
        """Create or refresh a conversation for a journal-style reference."""
        row = await self._database.fetchrow(
            """
            INSERT INTO conversations (user_id, reference)
            VALUES ($1::uuid, $2)
            ON CONFLICT (user_id, reference)
            DO UPDATE SET updated_at = NOW()
            RETURNING id::text AS id
            """,
            user_id,
            reference,
        )
        assert row is not None
        return row["id"]

    async def insert_message(
        self,
        *,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        client_message_id: str | None = None,
    ) -> str:
        """Persist a message with per-conversation sequence and idempotency."""
        idempotency_key = client_message_id or str(uuid.uuid4())
        row = await self._database.fetchrow(
            """
            INSERT INTO messages (conversation_id, user_id, role, content, client_message_id, sequence)
            VALUES (
              $1::uuid,
              $2::uuid,
              $3,
              $4,
              $5::uuid,
              COALESCE(
                (
                  SELECT MAX(m.sequence)
                  FROM messages m
                  WHERE m.conversation_id = $1::uuid
                ),
                0
              ) + 1
            )
            ON CONFLICT (conversation_id, client_message_id)
            DO UPDATE SET content = EXCLUDED.content
            RETURNING id::text AS id
            """,
            conversation_id,
            user_id,
            role,
            content,
            idempotency_key,
        )
        await self._database.execute(
            "UPDATE conversations SET updated_at = NOW() WHERE id = $1::uuid",
            conversation_id,
        )
        assert row is not None
        return row["id"]

    async def list_conversations(self, user_id: str, limit: int, before: str | None = None) -> Sequence[asyncpg.Record]:
        """List conversations ordered by descending reference with cursor pagination."""
        return await self._database.fetch(
            """
            SELECT
              c.id::text AS id,
              c.reference,
              c.created_at,
              c.updated_at,
              MAX(m.created_at) AS last_message_at,
              COUNT(m.id)::int AS message_count,
              'open'::text AS status
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.user_id = $1::uuid
              AND ($2::text IS NULL OR c.reference < $2)
            GROUP BY c.id
            ORDER BY c.reference DESC
            LIMIT $3
            """,
            user_id,
            before,
            limit,
        )

    async def get_conversation_by_reference(self, user_id: str, reference: str) -> asyncpg.Record | None:
        """Fetch one conversation summary for a reference."""
        return await self._database.fetchrow(
            """
            SELECT
              c.id::text AS id,
              c.reference,
              c.created_at,
              c.updated_at,
              MAX(m.created_at) AS last_message_at,
              COUNT(m.id)::int AS message_count,
              'open'::text AS status
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.user_id = $1::uuid AND c.reference = $2
            GROUP BY c.id
            """,
            user_id,
            reference,
        )

    async def list_messages(
        self,
        user_id: str,
        conversation_reference: str,
        limit: int,
        before_sequence: int | None = None,
    ) -> Sequence[asyncpg.Record]:
        """List conversation messages ordered from newest to oldest."""
        return await self._database.fetch(
            """
            SELECT
              m.id::text AS id,
              m.role,
              m.content,
              m.sequence,
              m.created_at,
              m.metadata
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.user_id = $1::uuid
              AND c.reference = $2
              AND ($3::int IS NULL OR m.sequence < $3)
            ORDER BY m.sequence DESC
            LIMIT $4
            """,
            user_id,
            conversation_reference,
            before_sequence,
            limit,
        )


    async def get_reference_by_conversation_id(self, conversation_id: str, user_id: str) -> str | None:
        """Resolve a conversation reference by id and user scope."""
        row = await self._database.fetchrow(
            """
            SELECT c.reference
            FROM conversations c
            WHERE c.id = $1::uuid AND c.user_id = $2::uuid
            """,
            conversation_id,
            user_id,
        )
        if row is None:
            return None
        return str(row["reference"])

    async def search_conversations(self, user_id: str, query: str, limit: int) -> Sequence[asyncpg.Record]:
        """Search conversations by reference or message content."""
        return await self._database.fetch(
            """
            SELECT
              c.id::text AS id,
              c.reference,
              c.created_at,
              c.updated_at,
              MAX(m.created_at) AS last_message_at,
              COUNT(m.id)::int AS message_count,
              'open'::text AS status
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.user_id = $1::uuid
              AND (m.content ILIKE ('%' || $2 || '%') OR c.reference ILIKE ('%' || $2 || '%'))
            GROUP BY c.id
            ORDER BY c.reference DESC
            LIMIT $3
            """,
            user_id,
            query,
            limit,
        )
