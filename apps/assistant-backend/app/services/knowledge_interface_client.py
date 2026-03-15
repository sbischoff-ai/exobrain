from __future__ import annotations

import grpc

from app.services.contracts import KnowledgeInterfaceClientProtocol
from app.services.grpc import knowledge_pb2, knowledge_pb2_grpc


class KnowledgeInterfaceClientError(Exception):
    """Base error for knowledge-interface RPC client failures."""


class KnowledgeInterfaceClientNotFoundError(KnowledgeInterfaceClientError):
    """Raised when requested knowledge-interface resource does not exist."""


class KnowledgeInterfaceClientAccessDeniedError(KnowledgeInterfaceClientError):
    """Raised when caller cannot access requested knowledge-interface resource."""


class KnowledgeInterfaceClientUnavailableError(KnowledgeInterfaceClientError):
    """Raised when knowledge-interface is unavailable or times out."""


class KnowledgeInterfaceClientInvalidArgumentError(KnowledgeInterfaceClientError):
    """Raised when knowledge-interface rejects request arguments."""


class KnowledgeInterfaceClient(KnowledgeInterfaceClientProtocol):
    """gRPC client for read/write APIs exposed by knowledge-interface."""

    def __init__(self, grpc_target: str, connect_timeout_seconds: float = 5.0) -> None:
        self._grpc_target = grpc_target
        self._connect_timeout_seconds = connect_timeout_seconds
        self._channel: grpc.aio.Channel | None = None
        self._stub: knowledge_pb2_grpc.KnowledgeInterfaceStub | None = None

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
            self._stub = None

    async def get_schema(self, *, universe_id: str) -> knowledge_pb2.GetSchemaReply:
        request = knowledge_pb2.GetSchemaRequest(universe_id=universe_id)
        return await self._call(self._get_or_create_stub().GetSchema, request, error_context="get schema")

    async def list_entities_by_type(
        self,
        *,
        user_id: str,
        type_id: str,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> knowledge_pb2.ListEntitiesByTypeReply:
        request = knowledge_pb2.ListEntitiesByTypeRequest(
            user_id=user_id,
            type_id=type_id,
            page_size=page_size,
            page_token=page_token,
        )
        return await self._call(
            self._get_or_create_stub().ListEntitiesByType,
            request,
            error_context="list entities by type",
        )

    async def get_entity_context(
        self,
        *,
        entity_id: str,
        user_id: str,
        max_block_level: int,
    ) -> knowledge_pb2.GetEntityContextReply:
        request = knowledge_pb2.GetEntityContextRequest(
            entity_id=entity_id,
            user_id=user_id,
            max_block_level=max_block_level,
        )
        return await self._call(
            self._get_or_create_stub().GetEntityContext,
            request,
            error_context="get entity context",
        )

    async def upsert_graph_delta(
        self,
        *,
        entities: list[knowledge_pb2.EntityNode],
        blocks: list[knowledge_pb2.BlockNode],
        edges: list[knowledge_pb2.GraphEdge],
        universes: list[knowledge_pb2.UniverseNode] | None = None,
    ) -> knowledge_pb2.UpsertGraphDeltaReply:
        request = knowledge_pb2.UpsertGraphDeltaRequest(
            entities=entities,
            blocks=blocks,
            edges=edges,
            universes=universes or [],
        )
        return await self._call(
            self._get_or_create_stub().UpsertGraphDelta,
            request,
            error_context="upsert graph delta",
        )

    async def _call(self, rpc, request, *, error_context: str):
        try:
            return await rpc(request, timeout=self._connect_timeout_seconds)
        except grpc.aio.AioRpcError as exc:
            status_code = exc.code()
            if status_code == grpc.StatusCode.INVALID_ARGUMENT:
                raise KnowledgeInterfaceClientInvalidArgumentError(
                    f"knowledge-interface rejected arguments for {error_context}",
                ) from exc
            if status_code == grpc.StatusCode.NOT_FOUND:
                raise KnowledgeInterfaceClientNotFoundError(f"knowledge-interface {error_context} not found") from exc
            if status_code in (grpc.StatusCode.PERMISSION_DENIED, grpc.StatusCode.UNAUTHENTICATED):
                raise KnowledgeInterfaceClientAccessDeniedError(
                    f"knowledge-interface {error_context} access denied",
                ) from exc
            if status_code in (grpc.StatusCode.DEADLINE_EXCEEDED, grpc.StatusCode.UNAVAILABLE):
                raise KnowledgeInterfaceClientUnavailableError(
                    f"knowledge-interface {error_context} unavailable",
                ) from exc
            raise KnowledgeInterfaceClientError(f"knowledge-interface failed to {error_context}") from exc

    def _get_or_create_stub(self) -> knowledge_pb2_grpc.KnowledgeInterfaceStub:
        if self._stub is None:
            self._channel = grpc.aio.insecure_channel(self._grpc_target)
            self._stub = knowledge_pb2_grpc.KnowledgeInterfaceStub(self._channel)
        return self._stub
