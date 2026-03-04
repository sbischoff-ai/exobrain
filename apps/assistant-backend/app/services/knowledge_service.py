from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from collections import defaultdict
from typing import Any

import grpc

from app.core.settings import Settings
from app.services.contracts import (
    DatabaseServiceProtocol,
    JobPublisherProtocol,
    KnowledgeInterfaceClientProtocol,
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


class KnowledgeNoPendingMessagesError(Exception):
    """Raised when there are no uncommitted messages to enqueue for knowledge updates."""


class KnowledgeEnqueueError(Exception):
    """Raised when knowledge update jobs cannot be enqueued."""

class KnowledgeService:
    def __init__(
        self,
        database: DatabaseServiceProtocol,
        job_publisher: JobPublisherProtocol,
        knowledge_interface_client: KnowledgeInterfaceClientProtocol,
        settings: Settings,
    ) -> None:
        self._database = database
        self._job_publisher = job_publisher
        self._knowledge_interface_client = knowledge_interface_client
        self._max_tokens = settings.knowledge_update_max_tokens

    async def list_wiki_category_tree(self, *, universe_id: str) -> list[dict[str, Any]]:
        """Return wiki categories as a deterministic parent/child tree.

        Multiple inheritance is represented by duplicating a child under each
        active parent category.
        """
        schema = await self._knowledge_interface_client.get_schema(universe_id=universe_id)

        categories_by_id: dict[str, dict[str, Any]] = {}
        category_parent_ids: dict[str, set[str]] = defaultdict(set)
        category_children_ids: dict[str, set[str]] = defaultdict(set)

        for node_type in schema.node_types:
            schema_type = node_type.type
            if not self._is_wiki_category_type(type_id=schema_type.id, kind=schema_type.kind, active=schema_type.active):
                continue
            categories_by_id[schema_type.id] = {
                "category_id": schema_type.id,
                "display_name": schema_type.name or schema_type.id,
            }

        for node_type in schema.node_types:
            child_type_id = node_type.type.id
            if child_type_id not in categories_by_id:
                continue

            for parent in node_type.parents:
                if not parent.active:
                    continue
                parent_type_id = parent.parent_type_id
                if parent_type_id not in categories_by_id:
                    continue

                category_parent_ids[child_type_id].add(parent_type_id)
                category_children_ids[parent_type_id].add(child_type_id)

        def sort_key(category_id: str) -> tuple[str, str]:
            category = categories_by_id[category_id]
            return (str(category["display_name"]).lower(), category_id)

        def build_sub_categories(category_id: str, *, lineage: frozenset[str]) -> list[dict[str, Any]]:
            sub_categories: list[dict[str, Any]] = []
            for child_id in sorted(category_children_ids.get(category_id, set()), key=sort_key):
                if child_id in lineage:
                    continue
                child_category = categories_by_id[child_id]
                sub_categories.append(
                    {
                        "category_id": child_category["category_id"],
                        "display_name": child_category["display_name"],
                        "sub_categories": build_sub_categories(child_id, lineage=lineage | {child_id}),
                    }
                )
            return sub_categories

        root_category_ids = sorted(
            [category_id for category_id in categories_by_id if not category_parent_ids.get(category_id)],
            key=sort_key,
        )

        root_categories: list[dict[str, Any]] = []
        for root_id in root_category_ids:
            root_category = categories_by_id[root_id]
            root_categories.append(
                {
                    "category_id": root_category["category_id"],
                    "display_name": root_category["display_name"],
                    "sub_categories": build_sub_categories(root_id, lineage=frozenset({root_id})),
                }
            )

        return root_categories

    async def enqueue_update_job(self, *, user_id: str, journal_reference: str | None = None) -> str:
        message_sequences = await self._list_uncommitted_message_sequences(user_id=user_id, journal_reference=journal_reference)
        if not message_sequences:
            raise KnowledgeNoPendingMessagesError("no uncommitted messages found for knowledge update")

        job_ids: list[str] = []
        for sequence in message_sequences:
            payload_messages = [self._message_payload(row) for row in sequence]
            payload_journal_reference = sequence[0]["reference"]
            try:
                job_id = await self._job_publisher.enqueue_job(
                    user_id=user_id,
                    job_type="knowledge.update",
                    payload={
                        "journal_reference": payload_journal_reference,
                        "messages": payload_messages,
                        "requested_by_user_id": user_id,
                    },
                )
            except grpc.aio.AioRpcError as exc:
                if exc.code() in (grpc.StatusCode.DEADLINE_EXCEEDED, grpc.StatusCode.UNAVAILABLE):
                    raise KnowledgeUpstreamUnavailableError("knowledge update enqueue unavailable") from exc
                raise KnowledgeEnqueueError("failed to enqueue knowledge update job") from exc
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
    def _is_wiki_category_type(*, type_id: str, kind: str, active: bool) -> bool:
        if not active:
            return False
        if kind != "node":
            return False
        return type_id.startswith("node.")

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
