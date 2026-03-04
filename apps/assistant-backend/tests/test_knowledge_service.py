from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import grpc
import pytest

from app.services.grpc import job_orchestrator_pb2, knowledge_pb2

from app.core.settings import Settings
from app.services.knowledge_service import (
    KnowledgeEnqueueError,
    KnowledgeJobAccessDeniedError,
    KnowledgeJobNotFoundError,
    KnowledgeNoPendingMessagesError,
    KnowledgeService,
    KnowledgeUpstreamUnavailableError,
    KnowledgeWatchError,
)


class FakeDatabase:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.fetch_calls: list[tuple[str, tuple[object, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetch(self, query: str, *args: object):
        self.fetch_calls.append((query, args))
        return self.rows

    async def execute(self, query: str, *args: object):
        self.execute_calls.append((query, args))
        return "UPDATE 1"


class FakeKnowledgeInterfaceClient:
    def __init__(
        self,
        reply: knowledge_pb2.GetSchemaReply | None = None,
        entities_reply: knowledge_pb2.ListEntitiesByTypeReply | None = None,
    ) -> None:
        self.reply = reply or knowledge_pb2.GetSchemaReply()
        self.entities_reply = entities_reply or knowledge_pb2.ListEntitiesByTypeReply()
        self.calls: list[dict[str, object]] = []

    async def get_schema(self, *, universe_id: str) -> knowledge_pb2.GetSchemaReply:
        self.calls.append({"method": "get_schema", "universe_id": universe_id})
        return self.reply

    async def list_entities_by_type(
        self,
        *,
        user_id: str,
        type_id: str,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> knowledge_pb2.ListEntitiesByTypeReply:
        self.calls.append(
            {
                "method": "list_entities_by_type",
                "user_id": user_id,
                "type_id": type_id,
                "page_size": page_size,
                "page_token": page_token,
            }
        )
        return self.entities_reply


class FakeJobPublisher:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.watch_calls: list[dict[str, object]] = []

    async def enqueue_job(self, *, user_id: str, job_type: str, payload: dict[str, object]) -> str:
        self.calls.append(
            {
                "user_id": user_id,
                "job_type": job_type,
                "payload": payload,
            }
        )
        return f"job-{len(self.calls)}"

    async def watch_job_status(self, *, job_id: str, include_current: bool = True) -> AsyncIterator[job_orchestrator_pb2.JobStatusEvent]:
        self.watch_calls.append({"job_id": job_id, "include_current": include_current})
        yield job_orchestrator_pb2.JobStatusEvent(
            job_id=job_id,
            state=job_orchestrator_pb2.STARTED,
            attempt=1,
            detail="working",
            terminal=False,
            emitted_at="2026-02-19T10:00:00Z",
        )
        yield job_orchestrator_pb2.JobStatusEvent(
            job_id=job_id,
            state=job_orchestrator_pb2.SUCCEEDED,
            attempt=1,
            detail="done",
            terminal=True,
            emitted_at="2026-02-19T10:01:00Z",
        )


class CustomEventJobPublisher(FakeJobPublisher):
    def __init__(self, events: list[job_orchestrator_pb2.JobStatusEvent]) -> None:
        super().__init__()
        self._events = events

    async def watch_job_status(self, *, job_id: str, include_current: bool = True) -> AsyncIterator[job_orchestrator_pb2.JobStatusEvent]:
        self.watch_calls.append({"job_id": job_id, "include_current": include_current})
        for event in self._events:
            yield event


@pytest.mark.asyncio
async def test_enqueue_update_job_filters_and_splits_uncommitted_sequences() -> None:
    rows = [
        {
            "id": "m-1",
            "reference": "2026/02/19",
            "role": "user",
            "content": "abcd",
            "sequence": 1,
            "created_at": datetime(2026, 2, 19, 10, 0, tzinfo=UTC),
            "committed_to_knowledge_base": False,
            "previous_committed": None,
        },
        {
            "id": "m-2",
            "reference": "2026/02/19",
            "role": "assistant",
            "content": "abcd",
            "sequence": 2,
            "created_at": datetime(2026, 2, 19, 10, 1, tzinfo=UTC),
            "committed_to_knowledge_base": True,
            "previous_committed": False,
        },
        {
            "id": "m-3",
            "reference": "2026/02/19",
            "role": "user",
            "content": "abcd",
            "sequence": 3,
            "created_at": datetime(2026, 2, 19, 10, 2, tzinfo=UTC),
            "committed_to_knowledge_base": False,
            "previous_committed": True,
        },
        {
            "id": "m-4",
            "reference": "2026/02/20",
            "role": "assistant",
            "content": "abcd",
            "sequence": 1,
            "created_at": datetime(2026, 2, 20, 10, 0, tzinfo=UTC),
            "committed_to_knowledge_base": False,
            "previous_committed": None,
        },
    ]
    database = FakeDatabase(rows)
    publisher = FakeJobPublisher()
    settings = Settings()
    settings.knowledge_update_max_tokens = 100
    service = KnowledgeService(database=database, job_publisher=publisher, knowledge_interface_client=FakeKnowledgeInterfaceClient(), settings=settings)

    job_id = await service.enqueue_update_job(user_id="user-1")

    assert job_id == "job-1"
    assert len(publisher.calls) == 3
    assert publisher.calls[0]["payload"]["journal_reference"] == "2026/02/19"
    assert publisher.calls[0]["user_id"] == "user-1"
    assert publisher.calls[0]["payload"]["requested_by_user_id"] == "user-1"
    assert [m["sequence"] for m in publisher.calls[0]["payload"]["messages"]] == [1]
    assert [m["sequence"] for m in publisher.calls[1]["payload"]["messages"]] == [3]
    assert publisher.calls[2]["payload"]["journal_reference"] == "2026/02/20"
    assert database.fetch_calls[0][1] == ("user-1", None)
    assert len(database.execute_calls) == 3


@pytest.mark.asyncio
async def test_enqueue_update_job_respects_token_limit() -> None:
    rows = [
        {
            "id": "m-1",
            "reference": "2026/02/19",
            "role": "user",
            "content": "a" * 24,
            "sequence": 1,
            "created_at": datetime(2026, 2, 19, 10, 0, tzinfo=UTC),
            "committed_to_knowledge_base": False,
            "previous_committed": None,
        },
        {
            "id": "m-2",
            "reference": "2026/02/19",
            "role": "assistant",
            "content": "b" * 24,
            "sequence": 2,
            "created_at": datetime(2026, 2, 19, 10, 1, tzinfo=UTC),
            "committed_to_knowledge_base": False,
            "previous_committed": False,
        },
    ]
    database = FakeDatabase(rows)
    publisher = FakeJobPublisher()
    settings = Settings()
    settings.knowledge_update_max_tokens = 10
    service = KnowledgeService(database=database, job_publisher=publisher, knowledge_interface_client=FakeKnowledgeInterfaceClient(), settings=settings)

    await service.enqueue_update_job(user_id="user-1", journal_reference="2026/02/19")

    assert len(publisher.calls) == 2
    assert database.fetch_calls[0][1] == ("user-1", "2026/02/19")


@pytest.mark.asyncio
async def test_enqueue_update_job_raises_when_no_uncommitted_messages() -> None:
    database = FakeDatabase([])
    publisher = FakeJobPublisher()
    service = KnowledgeService(database=database, job_publisher=publisher, knowledge_interface_client=FakeKnowledgeInterfaceClient(), settings=Settings())

    with pytest.raises(KnowledgeNoPendingMessagesError):
        await service.enqueue_update_job(user_id="user-1", journal_reference="2026/02/19")

    assert publisher.calls == []
    assert database.execute_calls == []


class EnqueueErroringJobPublisher(FakeJobPublisher):
    def __init__(self, code: grpc.StatusCode) -> None:
        super().__init__()
        self._code = code

    async def enqueue_job(self, *, user_id: str, job_type: str, payload: dict[str, object]) -> str:
        self.calls.append({"user_id": user_id, "job_type": job_type, "payload": payload})
        raise FakeAioRpcError(self._code)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (grpc.StatusCode.DEADLINE_EXCEEDED, KnowledgeUpstreamUnavailableError),
        (grpc.StatusCode.UNAVAILABLE, KnowledgeUpstreamUnavailableError),
        (grpc.StatusCode.INTERNAL, KnowledgeEnqueueError),
    ],
)
async def test_enqueue_update_job_maps_grpc_errors_to_domain_errors(status_code: grpc.StatusCode, expected_error: type[Exception]) -> None:
    rows = [
        {
            "id": "m-1",
            "reference": "2026/02/19",
            "role": "user",
            "content": "hello",
            "sequence": 1,
            "created_at": datetime(2026, 2, 19, 10, 0, tzinfo=UTC),
            "committed_to_knowledge_base": False,
            "previous_committed": None,
        }
    ]
    database = FakeDatabase(rows)
    service = KnowledgeService(
        database=database,
        job_publisher=EnqueueErroringJobPublisher(status_code),
        knowledge_interface_client=FakeKnowledgeInterfaceClient(),
        settings=Settings(),
    )

    with pytest.raises(expected_error):
        await service.enqueue_update_job(user_id="user-1", journal_reference="2026/02/19")

    assert database.execute_calls == []

@pytest.mark.asyncio
async def test_list_wiki_category_tree_filters_sorts_and_nests_types() -> None:
    schema = knowledge_pb2.GetSchemaReply(
        node_types=[
            knowledge_pb2.SchemaNodeType(type=knowledge_pb2.SchemaType(id="node.gamma", kind="node", name="Gamma", active=True)),
            knowledge_pb2.SchemaNodeType(type=knowledge_pb2.SchemaType(id="node.alpha", kind="node", name="Alpha", active=True)),
            knowledge_pb2.SchemaNodeType(type=knowledge_pb2.SchemaType(id="node.beta", kind="node", name="Beta", active=True)),
            knowledge_pb2.SchemaNodeType(type=knowledge_pb2.SchemaType(id="node.root", kind="node", name="Root", active=True)),
            knowledge_pb2.SchemaNodeType(type=knowledge_pb2.SchemaType(id="node.delta", kind="node", name="Delta", active=True)),
            knowledge_pb2.SchemaNodeType(type=knowledge_pb2.SchemaType(id="node.inactive", kind="node", name="Inactive", active=False)),
            knowledge_pb2.SchemaNodeType(type=knowledge_pb2.SchemaType(id="edge.related_to", kind="edge", name="Related", active=True)),
            knowledge_pb2.SchemaNodeType(type=knowledge_pb2.SchemaType(id="misc.type", kind="node", name="Misc", active=True)),
        ]
    )
    schema.node_types[0].parents.extend([
        knowledge_pb2.TypeInheritance(child_type_id="node.gamma", parent_type_id="node.beta", active=True),
        knowledge_pb2.TypeInheritance(child_type_id="node.gamma", parent_type_id="node.alpha", active=True),
    ])
    schema.node_types[2].parents.extend([
        knowledge_pb2.TypeInheritance(child_type_id="node.beta", parent_type_id="node.root", active=True),
    ])
    schema.node_types[1].parents.extend([
        knowledge_pb2.TypeInheritance(child_type_id="node.alpha", parent_type_id="node.root", active=True),
    ])

    client = FakeKnowledgeInterfaceClient(reply=schema)
    service = KnowledgeService(
        database=FakeDatabase([]),
        job_publisher=FakeJobPublisher(),
        knowledge_interface_client=client,
        settings=Settings(),
    )

    categories = await service.list_wiki_category_tree(universe_id="u-1")

    assert client.calls == [{"method": "get_schema", "universe_id": "u-1"}]
    assert categories == [
        {
            "category_id": "node.delta",
            "display_name": "Delta",
            "sub_categories": [],
        },
        {
            "category_id": "node.root",
            "display_name": "Root",
            "sub_categories": [
                {
                    "category_id": "node.alpha",
                    "display_name": "Alpha",
                    "sub_categories": [
                        {
                            "category_id": "node.gamma",
                            "display_name": "Gamma",
                            "sub_categories": [],
                        }
                    ],
                },
                {
                    "category_id": "node.beta",
                    "display_name": "Beta",
                    "sub_categories": [
                        {
                            "category_id": "node.gamma",
                            "display_name": "Gamma",
                            "sub_categories": [],
                        }
                    ],
                },
            ],
        },
    ]



@pytest.mark.asyncio
async def test_list_category_pages_maps_entity_fields_and_pagination() -> None:
    entities_reply = knowledge_pb2.ListEntitiesByTypeReply(
        entities=[
            knowledge_pb2.ListEntitiesByTypeItem(
                id="entity-1",
                name="Entity One",
                description="Entity summary",
                updated_at="2026-02-19T10:00:00Z",
                score=0.7,
            )
        ],
        next_page_token="next-cursor",
        total_count=42,
    )
    client = FakeKnowledgeInterfaceClient(entities_reply=entities_reply)
    service = KnowledgeService(
        database=FakeDatabase([]),
        job_publisher=FakeJobPublisher(),
        knowledge_interface_client=client,
        settings=Settings(),
    )

    response = await service.list_category_pages(
        user_id="user-1",
        category_id="type-1",
        page_size=20,
        page_token="cursor-1",
    )

    assert client.calls == [
        {
            "method": "list_entities_by_type",
            "user_id": "user-1",
            "type_id": "type-1",
            "page_size": 20,
            "page_token": "cursor-1",
        }
    ]
    assert response["page_size"] == 20
    assert response["next_page_token"] == "next-cursor"
    assert response["total_count"] == 42
    assert response["pages"][0]["entity"]["id"] == "entity-1"
    assert response["pages"][0]["page_id"] == "entity-1"
    assert response["pages"][0]["page_title"] == "Entity One"
    assert response["pages"][0]["page_summary"] == "Entity summary"

def test_count_text_tokens_rounds_character_division() -> None:
    assert KnowledgeService._count_text_tokens("abcd") == 1
    assert KnowledgeService._count_text_tokens("abcde") == 1
    assert KnowledgeService._count_text_tokens("abcdef") == 2


@pytest.mark.asyncio
async def test_watch_update_job_maps_orchestrator_events_to_stream_events() -> None:
    database = FakeDatabase([])
    publisher = FakeJobPublisher()
    service = KnowledgeService(database=database, job_publisher=publisher, knowledge_interface_client=FakeKnowledgeInterfaceClient(), settings=Settings())

    events = [event async for event in service.watch_update_job(user_id="user-1", job_id="job-1")]

    assert publisher.watch_calls == [{"job_id": "job-1", "include_current": True}]
    assert events == [
        {
            "type": "status",
            "data": {
                "job_id": "job-1",
                "state": "STARTED",
                "attempt": 1,
                "detail": "working",
                "terminal": False,
                "emitted_at": "2026-02-19T10:00:00Z",
            },
        },
        {
            "type": "status",
            "data": {
                "job_id": "job-1",
                "state": "SUCCEEDED",
                "attempt": 1,
                "detail": "done",
                "terminal": True,
                "emitted_at": "2026-02-19T10:01:00Z",
            },
        },
        {
            "type": "done",
            "data": {
                "job_id": "job-1",
                "state": "SUCCEEDED",
                "terminal": True,
            },
        },
    ]


@pytest.mark.asyncio
async def test_watch_update_job_stops_after_first_terminal_state() -> None:
    database = FakeDatabase([])
    publisher = CustomEventJobPublisher(
        [
            job_orchestrator_pb2.JobStatusEvent(
                job_id="job-1",
                state=job_orchestrator_pb2.SUCCEEDED,
                attempt=1,
                detail="done",
                terminal=True,
                emitted_at="2026-02-19T10:01:00Z",
            ),
            job_orchestrator_pb2.JobStatusEvent(
                job_id="job-1",
                state=job_orchestrator_pb2.FAILED_FINAL,
                attempt=2,
                detail="should not be emitted",
                terminal=True,
                emitted_at="2026-02-19T10:02:00Z",
            ),
        ]
    )
    service = KnowledgeService(database=database, job_publisher=publisher, knowledge_interface_client=FakeKnowledgeInterfaceClient(), settings=Settings())

    events = [event async for event in service.watch_update_job(user_id="user-1", job_id="job-1")]

    assert events == [
        {
            "type": "status",
            "data": {
                "job_id": "job-1",
                "state": "SUCCEEDED",
                "attempt": 1,
                "detail": "done",
                "terminal": True,
                "emitted_at": "2026-02-19T10:01:00Z",
            },
        },
        {
            "type": "done",
            "data": {"job_id": "job-1", "state": "SUCCEEDED", "terminal": True},
        },
    ]



class FakeAioRpcError(grpc.aio.AioRpcError):
    def __init__(self, code: grpc.StatusCode) -> None:
        self._status_code = code

    def code(self) -> grpc.StatusCode:
        return self._status_code


class ErroringJobPublisher(FakeJobPublisher):
    def __init__(self, code: grpc.StatusCode) -> None:
        super().__init__()
        self._code = code

    async def watch_job_status(self, *, job_id: str, include_current: bool = True) -> AsyncIterator[job_orchestrator_pb2.JobStatusEvent]:
        self.watch_calls.append({"job_id": job_id, "include_current": include_current})
        raise FakeAioRpcError(self._code)
        if False:
            yield job_orchestrator_pb2.JobStatusEvent()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (grpc.StatusCode.NOT_FOUND, KnowledgeJobNotFoundError),
        (grpc.StatusCode.PERMISSION_DENIED, KnowledgeJobAccessDeniedError),
        (grpc.StatusCode.UNAUTHENTICATED, KnowledgeJobAccessDeniedError),
        (grpc.StatusCode.DEADLINE_EXCEEDED, KnowledgeUpstreamUnavailableError),
        (grpc.StatusCode.UNAVAILABLE, KnowledgeUpstreamUnavailableError),
        (grpc.StatusCode.INTERNAL, KnowledgeWatchError),
    ],
)
async def test_watch_update_job_maps_grpc_errors_to_domain_errors(status_code: grpc.StatusCode, expected_error: type[Exception]) -> None:
    database = FakeDatabase([])
    service = KnowledgeService(database=database, job_publisher=ErroringJobPublisher(status_code), knowledge_interface_client=FakeKnowledgeInterfaceClient(), settings=Settings())

    with pytest.raises(expected_error):
        _ = [event async for event in service.watch_update_job(user_id="user-1", job_id="job-1")]
