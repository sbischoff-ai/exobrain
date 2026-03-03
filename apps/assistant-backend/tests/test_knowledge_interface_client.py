from __future__ import annotations

from types import SimpleNamespace

import grpc
import pytest

from app.services.knowledge_interface_client import (
    KnowledgeInterfaceClient,
    KnowledgeInterfaceClientAccessDeniedError,
    KnowledgeInterfaceClientError,
    KnowledgeInterfaceClientNotFoundError,
    KnowledgeInterfaceClientUnavailableError,
)


class _FakeChannel:
    def __init__(self, target: str) -> None:
        self.target = target
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class _FakeAioRpcError(grpc.aio.AioRpcError):
    def __init__(self, status_code: grpc.StatusCode):
        super().__init__(status_code, None, None)


class _FakeStub:
    def __init__(self, channel: _FakeChannel) -> None:
        self.channel = channel
        self.get_schema_requests = []
        self.list_entities_requests = []
        self.entity_context_requests = []

    async def GetSchema(self, request, timeout=None):  # noqa: N802
        self.get_schema_requests.append((request, timeout))
        return SimpleNamespace(node_types=[SimpleNamespace(type=SimpleNamespace(id="person"))])

    async def ListEntitiesByType(self, request, timeout=None):  # noqa: N802
        self.list_entities_requests.append((request, timeout))
        return SimpleNamespace(entities=[SimpleNamespace(id="entity-1")], next_page_token="next")

    async def GetEntityContext(self, request, timeout=None):  # noqa: N802
        self.entity_context_requests.append((request, timeout))
        return SimpleNamespace(entity=SimpleNamespace(id=request.entity_id), blocks=[])


@pytest.mark.asyncio
async def test_client_calls_get_schema_with_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    created_stubs: list[_FakeStub] = []

    monkeypatch.setattr("app.services.knowledge_interface_client.grpc.aio.insecure_channel", lambda target: _FakeChannel(target))

    def _fake_stub_factory(channel: _FakeChannel) -> _FakeStub:
        stub = _FakeStub(channel)
        created_stubs.append(stub)
        return stub

    monkeypatch.setattr("app.services.knowledge_interface_client.knowledge_pb2_grpc.KnowledgeInterfaceStub", _fake_stub_factory)

    client = KnowledgeInterfaceClient(grpc_target="localhost:50051", connect_timeout_seconds=1.5)

    response = await client.get_schema(universe_id="u1")

    assert response.node_types[0].type.id == "person"
    request, timeout = created_stubs[0].get_schema_requests[0]
    assert request.universe_id == "u1"
    assert timeout == 1.5


@pytest.mark.asyncio
async def test_client_calls_list_entities_and_entity_context(monkeypatch: pytest.MonkeyPatch) -> None:
    created_stubs: list[_FakeStub] = []

    monkeypatch.setattr("app.services.knowledge_interface_client.grpc.aio.insecure_channel", lambda target: _FakeChannel(target))

    def _fake_stub_factory(channel: _FakeChannel) -> _FakeStub:
        stub = _FakeStub(channel)
        created_stubs.append(stub)
        return stub

    monkeypatch.setattr("app.services.knowledge_interface_client.knowledge_pb2_grpc.KnowledgeInterfaceStub", _fake_stub_factory)

    client = KnowledgeInterfaceClient(grpc_target="localhost:50051")

    entities_reply = await client.list_entities_by_type(
        user_id="user-1",
        type_id="type-1",
        page_size=25,
        page_token="abc",
    )
    context_reply = await client.get_entity_context(entity_id="entity-1", user_id="user-1", max_block_level=2)

    assert entities_reply.entities[0].id == "entity-1"
    list_request, list_timeout = created_stubs[0].list_entities_requests[0]
    assert list_request.user_id == "user-1"
    assert list_request.type_id == "type-1"
    assert list_request.page_size == 25
    assert list_request.page_token == "abc"
    assert list_timeout == 5.0

    context_request, context_timeout = created_stubs[0].entity_context_requests[0]
    assert context_reply.entity.id == "entity-1"
    assert context_request.max_block_level == 2
    assert context_timeout == 5.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (grpc.StatusCode.NOT_FOUND, KnowledgeInterfaceClientNotFoundError),
        (grpc.StatusCode.PERMISSION_DENIED, KnowledgeInterfaceClientAccessDeniedError),
        (grpc.StatusCode.UNAVAILABLE, KnowledgeInterfaceClientUnavailableError),
        (grpc.StatusCode.INTERNAL, KnowledgeInterfaceClientError),
    ],
)
async def test_client_maps_grpc_errors(
    monkeypatch: pytest.MonkeyPatch,
    status_code: grpc.StatusCode,
    expected_error: type[Exception],
) -> None:
    class _ErroringStub:
        def __init__(self, _channel: _FakeChannel) -> None:
            pass

        async def GetSchema(self, _request, timeout=None):  # noqa: N802, ARG002
            raise _FakeAioRpcError(status_code)

    monkeypatch.setattr("app.services.knowledge_interface_client.grpc.aio.insecure_channel", lambda target: _FakeChannel(target))
    monkeypatch.setattr("app.services.knowledge_interface_client.knowledge_pb2_grpc.KnowledgeInterfaceStub", _ErroringStub)

    client = KnowledgeInterfaceClient(grpc_target="localhost:50051")

    with pytest.raises(expected_error):
        await client.get_schema(universe_id="u1")


@pytest.mark.asyncio
async def test_close_closes_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = _FakeChannel("localhost:50051")
    monkeypatch.setattr("app.services.knowledge_interface_client.grpc.aio.insecure_channel", lambda _target: channel)
    monkeypatch.setattr("app.services.knowledge_interface_client.knowledge_pb2_grpc.KnowledgeInterfaceStub", _FakeStub)

    client = KnowledgeInterfaceClient(grpc_target="localhost:50051")
    await client.get_schema(universe_id="u1")
    await client.close()

    assert channel.closed is True
