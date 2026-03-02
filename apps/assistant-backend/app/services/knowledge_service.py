from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.core.settings import Settings
from app.services.contracts import DatabaseServiceProtocol, JobPublisherProtocol


class KnowledgeService:
    def __init__(
        self,
        database: DatabaseServiceProtocol,
        job_publisher: JobPublisherProtocol,
        settings: Settings,
    ) -> None:
        self._database = database
        self._job_publisher = job_publisher
        self._max_tokens = settings.knowledge_update_max_tokens

    async def enqueue_update_job(self, *, user_id: str, journal_reference: str | None = None) -> str:
        message_sequences = await self._list_uncommitted_message_sequences(user_id=user_id, journal_reference=journal_reference)
        if not message_sequences:
            return ""

        job_ids: list[str] = []
        for sequence in message_sequences:
            payload_messages = [self._message_payload(row) for row in sequence]
            payload_journal_reference = sequence[0]["reference"]
            job_id = await self._job_publisher.enqueue_job(
                user_id=user_id,
                job_type="knowledge.update",
                payload={
                    "journal_reference": payload_journal_reference,
                    "messages": payload_messages,
                    "requested_by_user_id": user_id,
                },
            )
            job_ids.append(job_id)
            await self._mark_messages_committed([row["id"] for row in sequence])

        return job_ids[0]

    async def _list_uncommitted_message_sequences(
        self,
        *,
        user_id: str,
        journal_reference: str | None,
    ) -> list[list[dict[str, Any]]]:
        rows = await self._database.fetch(
            """
            SELECT
              m.id::text AS id,
              c.reference,
              m.role,
              m.content,
              m.sequence,
              m.created_at,
              m.committed_to_knowledge_base,
              LAG(m.committed_to_knowledge_base) OVER (
                PARTITION BY c.id
                ORDER BY m.sequence ASC
              ) AS previous_committed
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.user_id = $1::uuid
              AND ($2::text IS NULL OR c.reference = $2)
            ORDER BY c.reference ASC, m.sequence ASC
            """,
            user_id,
            journal_reference,
        )

        conversation_chunks: list[list[dict[str, Any]]] = []
        current_chunk: list[dict[str, Any]] = []
        current_reference: str | None = None

        for raw_row in rows:
            row = dict(raw_row)
            if row["committed_to_knowledge_base"]:
                if current_chunk:
                    conversation_chunks.extend(self._split_by_token_limit(current_chunk))
                    current_chunk = []
                current_reference = row["reference"]
                continue

            if current_reference is None:
                current_reference = row["reference"]

            if row["reference"] != current_reference:
                if current_chunk:
                    conversation_chunks.extend(self._split_by_token_limit(current_chunk))
                    current_chunk = []
                current_reference = row["reference"]

            if row.get("previous_committed") is True and current_chunk:
                conversation_chunks.extend(self._split_by_token_limit(current_chunk))
                current_chunk = []

            current_chunk.append(row)

        if current_chunk:
            conversation_chunks.extend(self._split_by_token_limit(current_chunk))

        return conversation_chunks

    def _split_by_token_limit(self, rows: Sequence[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        chunks: list[list[dict[str, Any]]] = []
        chunk: list[dict[str, Any]] = []
        chunk_tokens = 0

        for row in rows:
            message_tokens = self._count_text_tokens(row.get("content"))
            if chunk and chunk_tokens + message_tokens > self._max_tokens:
                chunks.append(chunk)
                chunk = []
                chunk_tokens = 0

            chunk.append(row)
            chunk_tokens += message_tokens

        if chunk:
            chunks.append(chunk)
        return chunks

    @staticmethod
    def _count_text_tokens(text: str | None) -> int:
        if not text:
            return 0
        return round(len(text) / 4)

    @staticmethod
    def _message_payload(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "role": row.get("role"),
            "content": row.get("content"),
            "sequence": row.get("sequence"),
            "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
        }

    async def _mark_messages_committed(self, message_ids: Sequence[str]) -> None:
        if not message_ids:
            return
        await self._database.execute(
            """
            UPDATE messages
            SET committed_to_knowledge_base = TRUE
            WHERE id = ANY($1::uuid[])
            """,
            message_ids,
        )
