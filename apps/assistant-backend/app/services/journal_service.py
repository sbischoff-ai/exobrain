from __future__ import annotations

from datetime import UTC, datetime
import uuid

from app.services.database_service import DatabaseService


class JournalService:
    def __init__(self, database: DatabaseService) -> None:
        self._database = database

    async def ensure_conversation(self, user_id: str, reference: str) -> str:
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
        if client_message_id is None:
            client_message_id = str(uuid.uuid4())
        row = await self._database.fetchrow(
            """
            INSERT INTO messages (conversation_id, user_id, role, content, client_message_id)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid)
            ON CONFLICT (conversation_id, client_message_id)
            DO UPDATE SET content = EXCLUDED.content
            RETURNING id::text AS id
            """,
            conversation_id,
            user_id,
            role,
            content,
            client_message_id,
        )
        await self._database.execute("UPDATE conversations SET updated_at = NOW() WHERE id = $1::uuid", conversation_id)
        assert row is not None
        return row["id"]

    async def list_journals(self, user_id: str, limit: int, before: str | None = None):
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

    async def get_journal(self, user_id: str, reference: str):
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

    async def list_messages(self, user_id: str, reference: str, limit: int):
        return await self._database.fetch(
            """
            SELECT
              m.id::text AS id,
              m.role,
              m.content,
              m.created_at,
              m.metadata
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.user_id = $1::uuid AND c.reference = $2
            ORDER BY m.created_at ASC
            LIMIT $3
            """,
            user_id,
            reference,
            limit,
        )

    @staticmethod
    def today_reference() -> str:
        return datetime.now(UTC).strftime("%Y/%m/%d")
