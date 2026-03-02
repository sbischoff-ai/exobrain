from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

import grpc

from app.core.settings import Settings
from app.services.contracts import (
    DatabaseServiceProtocol,
    JobPublisherProtocol,
    KnowledgeJobStatusSSEPayload,
)
from app.services.grpc import job_orchestrator_pb2
from app.services.knowledge_stream import (
    KnowledgeUpdateDoneEventData,
    KnowledgeUpdateStatusEventData,
    KnowledgeUpdateStreamEvent,
)


class KnowledgeWatchError(Exception):
    """Base domain error for watch-stream failures."""


class KnowledgeJobNotFoundError(KnowledgeWatchError):
    """Raised when a requested knowledge update job id does not exist."""


class KnowledgeJobAccessDeniedError(KnowledgeWatchError):
    """Raised when a user cannot access the requested job stream."""


class KnowledgeUpstreamUnavailableError(KnowledgeWatchError):
    """Raised when the job orchestrator is unavailable during stream watch."""

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


    async def watch_update_job(
        self,
        *,
        user_id: str,
        job_id: str,
        include_current: bool = True,
    ) -> AsyncIterator[KnowledgeUpdateStreamEvent]:
        del user_id
        try:
            async for event in self._job_publisher.watch_job_status(job_id=job_id, include_current=include_current):
                payload: KnowledgeJobStatusSSEPayload = {
                    "job_id": event.job_id,
                    "state": job_orchestrator_pb2.JobLifecycleState.Name(event.state),
                    "attempt": event.attempt,
                    "detail": event.detail,
                    "terminal": event.terminal,
                    "emitted_at": event.emitted_at,
                }
                status_event: KnowledgeUpdateStatusEventData = payload
                yield {"type": "status", "data": status_event}

                if payload["terminal"]:
                    done_event: KnowledgeUpdateDoneEventData = {
                        "job_id": payload["job_id"],
                        "state": payload["state"],
                        "terminal": payload["terminal"],
                    }
                    yield {"type": "done", "data": done_event}
                    return
        except grpc.aio.AioRpcError as exc:
            status_code = exc.code()
            if status_code == grpc.StatusCode.NOT_FOUND:
                raise KnowledgeJobNotFoundError(f"knowledge update job not found: {job_id}") from exc
            if status_code in (grpc.StatusCode.PERMISSION_DENIED, grpc.StatusCode.UNAUTHENTICATED):
                raise KnowledgeJobAccessDeniedError(f"knowledge update job access denied: {job_id}") from exc
            if status_code in (grpc.StatusCode.DEADLINE_EXCEEDED, grpc.StatusCode.UNAVAILABLE):
                raise KnowledgeUpstreamUnavailableError("knowledge update stream unavailable") from exc
            raise KnowledgeWatchError("failed to watch knowledge update job") from exc

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
