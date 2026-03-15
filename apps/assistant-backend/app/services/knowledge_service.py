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
from app.services.grpc import job_orchestrator_pb2, knowledge_pb2
from app.services.knowledge_interface_client import (
    KnowledgeInterfaceClientAccessDeniedError,
    KnowledgeInterfaceClientError,
    KnowledgeInterfaceClientInvalidArgumentError,
    KnowledgeInterfaceClientNotFoundError,
    KnowledgeInterfaceClientUnavailableError,
)
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


class KnowledgePageNotFoundError(Exception):
    """Raised when the requested page entity does not exist."""


class KnowledgePageAccessDeniedError(Exception):
    """Raised when the requested page entity is not accessible."""


class KnowledgePageUnavailableError(Exception):
    """Raised when page lookup fails due to unavailable upstream service."""


class KnowledgePageUpstreamError(Exception):
    """Raised when page lookup fails due to upstream service errors."""


class KnowledgePageInvalidBlockError(Exception):
    """Raised when one or more page block updates are invalid."""


class KnowledgeService:
    _PAGE_DETAIL_EXCLUDED_PROPERTY_KEYS = {
        "created_at",
        "updated_at",
        "visibility",
        "user_id",
        "type_id",
        "id",
    }

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

    async def list_wiki_category_tree(
        self, *, universe_id: str
    ) -> list[dict[str, Any]]:
        """Return wiki categories as a deterministic parent/child tree.
        Multiple inheritance is represented by duplicating a child under each
        active parent category.
        """
        schema = await self._knowledge_interface_client.get_schema(
            universe_id=universe_id
        )
        excluded_root_types = {"node.block", "node.universe"}
        categories_by_id: dict[str, dict[str, Any]] = {}
        all_children_by_parent: dict[str, set[str]] = defaultdict(set)
        for node_type in schema.node_types:
            schema_type = node_type.type
            if not self._is_wiki_category_type(
                type_id=schema_type.id, kind=schema_type.kind, active=schema_type.active
            ):
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
                all_children_by_parent[parent_type_id].add(child_type_id)

        root_category_ids = sorted(
            [
                child_id
                for child_id in all_children_by_parent.get("node.entity", set())
                if child_id not in excluded_root_types
            ]
        )

        included_category_ids: set[str] = set(root_category_ids)
        pending_ids = list(root_category_ids)
        while pending_ids:
            parent_id = pending_ids.pop()
            for child_id in all_children_by_parent.get(parent_id, set()):
                if child_id in included_category_ids:
                    continue
                included_category_ids.add(child_id)
                pending_ids.append(child_id)

        category_children_ids: dict[str, set[str]] = defaultdict(set)
        for parent_id, child_ids in all_children_by_parent.items():
            if parent_id not in included_category_ids:
                continue
            for child_id in child_ids:
                if child_id in included_category_ids:
                    category_children_ids[parent_id].add(child_id)

        def sort_key(category_id: str) -> tuple[str, str]:
            category = categories_by_id[category_id]
            return (str(category["display_name"]).lower(), category_id)

        def build_sub_categories(
            category_id: str, *, lineage: frozenset[str]
        ) -> list[dict[str, Any]]:
            sub_categories: list[dict[str, Any]] = []
            for child_id in sorted(
                category_children_ids.get(category_id, set()), key=sort_key
            ):
                if child_id in lineage:
                    continue
                child_category = categories_by_id[child_id]
                sub_categories.append(
                    {
                        "category_id": child_category["category_id"],
                        "display_name": child_category["display_name"],
                        "sub_categories": build_sub_categories(
                            child_id, lineage=lineage | {child_id}
                        ),
                    }
                )
            return sub_categories

        root_category_ids = sorted(root_category_ids, key=sort_key)
        root_categories: list[dict[str, Any]] = []
        for root_id in root_category_ids:
            root_category = categories_by_id[root_id]
            root_categories.append(
                {
                    "category_id": root_category["category_id"],
                    "display_name": root_category["display_name"],
                    "sub_categories": build_sub_categories(
                        root_id, lineage=frozenset({root_id})
                    ),
                }
            )
        return root_categories

    async def list_category_pages(
        self,
        *,
        user_id: str,
        category_id: str,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        reply = await self._knowledge_interface_client.list_entities_by_type(
            user_id=user_id,
            type_id=category_id,
            page_size=page_size,
            page_token=page_token,
        )
        knowledge_pages: list[dict[str, Any]] = []
        for entity in reply.entities:
            knowledge_pages.append(
                {
                    "id": entity.id,
                    "title": entity.name,
                    "summary": entity.description if entity.HasField("description") else None,
                    "metadata": {
                        "created_at": "",
                        "updated_at": entity.updated_at
                        if entity.HasField("updated_at")
                        else "",
                    },
                }
            )
        return {
            "knowledge_pages": knowledge_pages,
            "page_size": page_size if page_size is not None else max(len(knowledge_pages), 1),
            "next_page_token": reply.next_page_token
            if reply.HasField("next_page_token")
            else None,
            "total_count": reply.total_count if reply.HasField("total_count") else None,
        }

    async def get_page_detail(self, *, user_id: str, page_id: str) -> dict[str, Any]:
        try:
            reply = await self._knowledge_interface_client.get_entity_context(
                entity_id=page_id,
                user_id=user_id,
                max_block_level=2,
            )
        except KnowledgeInterfaceClientNotFoundError as exc:
            raise KnowledgePageNotFoundError("knowledge page not found") from exc
        except KnowledgeInterfaceClientAccessDeniedError as exc:
            raise KnowledgePageAccessDeniedError(
                "knowledge page access denied"
            ) from exc
        except KnowledgeInterfaceClientUnavailableError as exc:
            raise KnowledgePageUnavailableError("knowledge page unavailable") from exc
        except KnowledgeInterfaceClientError as exc:
            raise KnowledgePageUpstreamError("knowledge page upstream failure") from exc
        entity = reply.entity
        links: list[dict[str, str | None]] = []
        seen_link_page_ids: set[str] = set()
        for neighbor in reply.neighbors:
            other_entity = neighbor.other_entity
            if other_entity.id in seen_link_page_ids:
                continue
            seen_link_page_ids.add(other_entity.id)
            links.append(
                {
                    "page_id": other_entity.id,
                    "title": other_entity.name,
                    "summary": other_entity.description
                    if other_entity.HasField("description")
                    else None,
                }
            )
        properties = {
            key: value
            for key, value in reply.entity_properties.items()
            if key not in self._PAGE_DETAIL_EXCLUDED_PROPERTY_KEYS
        }
        return {
            "id": entity.id,
            "category_id": entity.type_id,
            "title": entity.name,
            "summary": self._extract_summary_from_described_by_block(reply.blocks),
            "metadata": {
                "created_at": entity.created_at
                if entity.HasField("created_at")
                else "",
                "updated_at": entity.updated_at
                if entity.HasField("updated_at")
                else "",
            },
            "properties": properties,
            "links": links,
            "content_blocks": self._map_content_blocks(reply.blocks),
        }

    async def update_page_blocks(
        self,
        *,
        user_id: str,
        page_id: str,
        content_blocks: list[dict[str, str]],
    ) -> dict[str, Any]:
        block_ids = [item["block_id"].strip() for item in content_blocks]
        if any(not block_id for block_id in block_ids):
            raise KnowledgePageInvalidBlockError("invalid knowledge page block id")

        block_updates = [
            knowledge_pb2.BlockNode(
                id=block_id,
                type_id="node.block",
                properties=[
                    knowledge_pb2.PropertyValue(
                        key="text",
                        string_value=item["markdown_content"],
                    )
                ],
                user_id=user_id,
                visibility=knowledge_pb2.PRIVATE,
            )
            for block_id, item in zip(block_ids, content_blocks)
        ]

        try:
            await self._knowledge_interface_client.upsert_graph_delta(
                entities=[],
                blocks=block_updates,
                edges=[],
            )
        except KnowledgeInterfaceClientInvalidArgumentError as exc:
            raise KnowledgePageInvalidBlockError("invalid knowledge page block update") from exc
        except KnowledgeInterfaceClientNotFoundError as exc:
            raise KnowledgePageNotFoundError("knowledge page not found") from exc
        except KnowledgeInterfaceClientAccessDeniedError as exc:
            raise KnowledgePageAccessDeniedError("knowledge page access denied") from exc
        except KnowledgeInterfaceClientUnavailableError as exc:
            raise KnowledgePageUnavailableError("knowledge page unavailable") from exc
        except KnowledgeInterfaceClientError as exc:
            raise KnowledgePageUpstreamError("knowledge page upstream failure") from exc

        return {
            "page_id": page_id,
            "updated_block_ids": block_ids,
            "updated_block_count": len(block_ids),
            "status": "updated",
        }

    async def enqueue_update_job(
        self, *, user_id: str, journal_reference: str | None = None
    ) -> str:
        message_sequences = await self._list_uncommitted_message_sequences(
            user_id=user_id, journal_reference=journal_reference
        )
        if not message_sequences:
            raise KnowledgeNoPendingMessagesError(
                "no uncommitted messages found for knowledge update"
            )
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
                if exc.code() in (
                    grpc.StatusCode.DEADLINE_EXCEEDED,
                    grpc.StatusCode.UNAVAILABLE,
                ):
                    raise KnowledgeUpstreamUnavailableError(
                        "knowledge update enqueue unavailable"
                    ) from exc
                raise KnowledgeEnqueueError(
                    "failed to enqueue knowledge update job"
                ) from exc
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
            async for event in self._job_publisher.watch_job_status(
                job_id=job_id, include_current=include_current
            ):
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
                raise KnowledgeJobNotFoundError(
                    f"knowledge update job not found: {job_id}"
                ) from exc
            if status_code in (
                grpc.StatusCode.PERMISSION_DENIED,
                grpc.StatusCode.UNAUTHENTICATED,
            ):
                raise KnowledgeJobAccessDeniedError(
                    f"knowledge update job access denied: {job_id}"
                ) from exc
            if status_code in (
                grpc.StatusCode.DEADLINE_EXCEEDED,
                grpc.StatusCode.UNAVAILABLE,
            ):
                raise KnowledgeUpstreamUnavailableError(
                    "knowledge update stream unavailable"
                ) from exc
            raise KnowledgeWatchError("failed to watch knowledge update job") from exc

    @staticmethod
    def _map_content_blocks(blocks: Any) -> list[dict[str, str]]:
        grouped: dict[str | None, list[Any]] = defaultdict(list)
        for block in blocks:
            parent_block_id = (
                block.parent_block_id if block.HasField("parent_block_id") else None
            )
            grouped[parent_block_id].append(block)
        for siblings in grouped.values():
            siblings.sort(key=lambda block: (block.block_level, block.id))

        content_blocks: list[dict[str, str]] = []

        def walk(parent_id: str | None) -> None:
            for block in grouped.get(parent_id, []):
                text = block.text if block.HasField("text") else ""
                if text.strip():
                    content_blocks.append({"block_id": block.id, "markdown": text.strip()})
                walk(block.id)

        walk(None)
        return content_blocks

    @staticmethod
    def _extract_summary_from_described_by_block(blocks: Any) -> str | None:
        for block in blocks:
            is_root = not block.HasField("parent_block_id")
            text = block.text if block.HasField("text") else ""
            if is_root and block.block_level == 0 and text.strip():
                return text.strip()
        return None

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
                    conversation_chunks.extend(
                        self._split_by_token_limit(current_chunk)
                    )
                    current_chunk = []
                current_reference = row["reference"]
                continue
            if current_reference is None:
                current_reference = row["reference"]
            if row["reference"] != current_reference:
                if current_chunk:
                    conversation_chunks.extend(
                        self._split_by_token_limit(current_chunk)
                    )
                    current_chunk = []
                current_reference = row["reference"]
            if row.get("previous_committed") is True and current_chunk:
                conversation_chunks.extend(self._split_by_token_limit(current_chunk))
                current_chunk = []
            current_chunk.append(row)
        if current_chunk:
            conversation_chunks.extend(self._split_by_token_limit(current_chunk))
        return conversation_chunks

    def _split_by_token_limit(
        self, rows: Sequence[dict[str, Any]]
    ) -> list[list[dict[str, Any]]]:
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
            "created_at": row.get("created_at").isoformat()
            if row.get("created_at")
            else None,
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
