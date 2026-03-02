from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import grpc
import pytest
from pydantic import BaseModel

from app.contracts import JobEnvelope
from app.transport.grpc import job_orchestrator_pb2, job_orchestrator_pb2_grpc
from app.transport.grpc.service import JobOrchestratorServicer
from app.worker.job_registry import JOB_PAYLOAD_MODEL_BY_TYPE


class _StatusSubscription:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.unsubscribed = False

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        item = await self._queue.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def publish(self, payload: bytes) -> None:
        await self._queue.put(payload)

    async def close(self) -> None:
        await self._queue.put(None)

    async def unsubscribe(self) -> None:
        self.unsubscribed = True


async def _wait_for_subscription(subscriptions: dict[str, _StatusSubscription], subject: str) -> _StatusSubscription:
    for _ in range(50):
        sub = subscriptions.get(subject)
        if sub is not None:
            return sub
        await asyncio.sleep(0.01)
    raise AssertionError(f"subscription not created for {subject}")


@pytest.fixture
async def grpc_orchestrator_stub() -> tuple[
    job_orchestrator_pb2_grpc.JobOrchestratorStub,
    list[tuple[str, bytes]],
    dict[str, _StatusSubscription],
    dict[str, dict[str, object]],
]:
    published: list[tuple[str, bytes]] = []
    status_subscriptions: dict[str, _StatusSubscription] = {}
    status_snapshots: dict[str, dict[str, object]] = {}

    async def publish(subject: str, payload: bytes) -> None:
        published.append((subject, payload))

    async def fetch_status(job_id: str) -> dict[str, object] | None:
        return status_snapshots.get(job_id)

    async def subscribe_status(subject: str) -> _StatusSubscription:
        sub = _StatusSubscription()
        status_subscriptions[subject] = sub
        return sub

    server = grpc.aio.server()
    job_orchestrator_pb2_grpc.add_JobOrchestratorServicer_to_server(
        JobOrchestratorServicer(
            publish,
            fetch_job_status=fetch_status,
            subscribe_job_status=subscribe_status,
        ),
        server,
    )
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()

    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    stub = job_orchestrator_pb2_grpc.JobOrchestratorStub(channel)

    try:
        yield stub, published, status_subscriptions, status_snapshots
    finally:
        await channel.close()
        await server.stop(grace=None)


@pytest.mark.asyncio
async def test_enqueue_job_success_publishes_expected_subject_and_job_id(
    grpc_orchestrator_stub: tuple[
        job_orchestrator_pb2_grpc.JobOrchestratorStub,
        list[tuple[str, bytes]],
        dict[str, _StatusSubscription],
        dict[str, dict[str, object]],
    ]
) -> None:
    stub, published, _, _ = grpc_orchestrator_stub

    reply = await stub.EnqueueJob(
        job_orchestrator_pb2.EnqueueJobRequest(
            job_type="knowledge.update",
            user_id="user-1",
            knowledge_update=job_orchestrator_pb2.KnowledgeUpdatePayload(
                journal_reference="2026/02/24",
                requested_by_user_id="user-1",
                messages=[job_orchestrator_pb2.KnowledgeUpdateMessage(role="user", content="hello")],
            ),
        )
    )

    assert reply.job_id
    UUID(reply.job_id)
    assert len(published) == 2
    subject, _ = published[0]
    assert subject == "jobs.knowledge.update.requested"
    status_subject, status_payload = published[1]
    assert status_subject == f"jobs.status.{reply.job_id}"
    # Ensure emitted payload shape is parseable JSON and carries initial status.
    decoded = json.loads(status_payload.decode("utf-8"))
    assert decoded["state"] == "ENQUEUED_OR_PENDING"


@pytest.mark.asyncio
async def test_enqueue_job_invalid_payload_or_job_type_returns_grpc_error(
    grpc_orchestrator_stub: tuple[
        job_orchestrator_pb2_grpc.JobOrchestratorStub,
        list[tuple[str, bytes]],
        dict[str, _StatusSubscription],
        dict[str, dict[str, object]],
    ]
) -> None:
    stub, _, _, _ = grpc_orchestrator_stub

    with pytest.raises(grpc.aio.AioRpcError) as job_type_error:
        await stub.EnqueueJob(
            job_orchestrator_pb2.EnqueueJobRequest(
                job_type="unknown.job",
                user_id="user-1",
                payload_json=json.dumps({"value": "x"}),
            )
        )

    assert job_type_error.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "unsupported job_type" in job_type_error.value.details()

    with pytest.raises(grpc.aio.AioRpcError) as payload_error:
        await stub.EnqueueJob(
            job_orchestrator_pb2.EnqueueJobRequest(
                job_type="knowledge.update",
                user_id="user-1",
            )
        )

    assert payload_error.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "knowledge_update payload is required" in payload_error.value.details()


@pytest.mark.asyncio
async def test_enqueue_job_generates_envelope_matching_contract(
    grpc_orchestrator_stub: tuple[
        job_orchestrator_pb2_grpc.JobOrchestratorStub,
        list[tuple[str, bytes]],
        dict[str, _StatusSubscription],
        dict[str, dict[str, object]],
    ]
) -> None:
    stub, published, _, _ = grpc_orchestrator_stub

    reply = await stub.EnqueueJob(
        job_orchestrator_pb2.EnqueueJobRequest(
            job_type="knowledge.update",
            user_id="user-1",
            knowledge_update=job_orchestrator_pb2.KnowledgeUpdatePayload(
                journal_reference="2026/02/24",
                requested_by_user_id="user-1",
                messages=[job_orchestrator_pb2.KnowledgeUpdateMessage(role="assistant", sequence=2)],
            ),
        )
    )

    _, envelope_bytes = published[0]
    envelope = JobEnvelope.model_validate_json(envelope_bytes.decode("utf-8"))

    assert envelope.job_id == reply.job_id
    assert envelope.job_type == "knowledge.update"
    assert envelope.correlation_id == "user-1"
    assert envelope.schema_version == 1
    assert envelope.attempt == 0
    assert envelope.payload["requested_by_user_id"] == "user-1"


@pytest.mark.asyncio
async def test_watch_job_status_happy_path_streams_started_then_succeeded_and_closes(
    grpc_orchestrator_stub: tuple[
        job_orchestrator_pb2_grpc.JobOrchestratorStub,
        list[tuple[str, bytes]],
        dict[str, _StatusSubscription],
        dict[str, dict[str, object]],
    ]
) -> None:
    stub, _, subscriptions, _ = grpc_orchestrator_stub
    job_id = str(uuid4())

    stream = stub.WatchJobStatus(job_orchestrator_pb2.WatchJobStatusRequest(job_id=job_id))
    first_event = asyncio.create_task(stream.read())
    subscription = await _wait_for_subscription(subscriptions, f"jobs.status.{job_id}")

    await subscription.publish(
        json.dumps({"job_id": job_id, "state": "STARTED", "attempt": 1, "terminal": False, "emitted_at": datetime.now(timezone.utc).isoformat()}).encode(
            "utf-8"
        )
    )
    await subscription.publish(
        json.dumps({"job_id": job_id, "state": "SUCCEEDED", "attempt": 1, "terminal": True, "emitted_at": datetime.now(timezone.utc).isoformat()}).encode(
            "utf-8"
        )
    )

    events = [await first_event]
    while True:
        event = await stream.read()
        if event == grpc.aio.EOF:
            break
        events.append(event)

    assert [event.state for event in events] == [job_orchestrator_pb2.STARTED, job_orchestrator_pb2.SUCCEEDED]
    assert subscription.unsubscribed is True


@pytest.mark.asyncio
async def test_watch_job_status_retry_then_terminal_failure_closes(
    grpc_orchestrator_stub: tuple[
        job_orchestrator_pb2_grpc.JobOrchestratorStub,
        list[tuple[str, bytes]],
        dict[str, _StatusSubscription],
        dict[str, dict[str, object]],
    ]
) -> None:
    stub, _, subscriptions, _ = grpc_orchestrator_stub
    job_id = str(uuid4())

    stream = stub.WatchJobStatus(job_orchestrator_pb2.WatchJobStatusRequest(job_id=job_id))
    first_event = asyncio.create_task(stream.read())
    subscription = await _wait_for_subscription(subscriptions, f"jobs.status.{job_id}")

    await subscription.publish(
        json.dumps(
            {
                "job_id": job_id,
                "state": "RETRYING",
                "attempt": 1,
                "detail": "temporary",
                "terminal": False,
                "emitted_at": datetime.now(timezone.utc).isoformat(),
            }
        ).encode("utf-8")
    )
    await subscription.publish(
        json.dumps(
            {
                "job_id": job_id,
                "state": "FAILED_FINAL",
                "attempt": 3,
                "detail": "boom",
                "terminal": True,
                "emitted_at": datetime.now(timezone.utc).isoformat(),
            }
        ).encode("utf-8")
    )

    events = [await first_event]
    while True:
        event = await stream.read()
        if event == grpc.aio.EOF:
            break
        events.append(event)
    assert [event.state for event in events] == [job_orchestrator_pb2.RETRYING, job_orchestrator_pb2.FAILED_FINAL]
    assert events[-1].terminal is True
    assert subscriptions[f"jobs.status.{job_id}"].unsubscribed is True


@pytest.mark.asyncio
async def test_watch_job_status_include_current_not_found_returns_not_found(
    grpc_orchestrator_stub: tuple[
        job_orchestrator_pb2_grpc.JobOrchestratorStub,
        list[tuple[str, bytes]],
        dict[str, _StatusSubscription],
        dict[str, dict[str, object]],
    ]
) -> None:
    stub, _, _, _ = grpc_orchestrator_stub

    with pytest.raises(grpc.aio.AioRpcError) as error:
        call = stub.WatchJobStatus(
            job_orchestrator_pb2.WatchJobStatusRequest(job_id=str(uuid4()), include_current=True)
        )
        await call.read()

    assert error.value.code() == grpc.StatusCode.NOT_FOUND


@pytest.mark.asyncio
async def test_enqueue_job_validates_payload_schema() -> None:
    class StrictKnowledgePayload(BaseModel):
        required_field: str

    async def publish(_: str, __: bytes) -> None:
        return None

    original_model = JOB_PAYLOAD_MODEL_BY_TYPE["knowledge.update"]
    JOB_PAYLOAD_MODEL_BY_TYPE["knowledge.update"] = StrictKnowledgePayload
    try:
        servicer = JobOrchestratorServicer(publish)

        class _Context:
            async def abort(self, *, code: grpc.StatusCode, details: str):
                raise RuntimeError(f"{code.name}:{details}")

        with pytest.raises(RuntimeError) as exc_info:
            await servicer.EnqueueJob(
                job_orchestrator_pb2.EnqueueJobRequest(
                    job_type="knowledge.update",
                    user_id="user-1",
                    knowledge_update=job_orchestrator_pb2.KnowledgeUpdatePayload(
                        journal_reference="2026/02/24",
                        requested_by_user_id="user-1",
                    ),
                ),
                _Context(),
            )
    finally:
        JOB_PAYLOAD_MODEL_BY_TYPE["knowledge.update"] = original_model

    assert "INVALID_ARGUMENT" in str(exc_info.value)
    assert "required_field" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "is_terminal", "expected_state", "expected_terminal"),
    [
        ("requested", False, job_orchestrator_pb2.ENQUEUED_OR_PENDING, False),
        ("processing", False, job_orchestrator_pb2.STARTED, False),
        ("retrying", False, job_orchestrator_pb2.RETRYING, False),
        ("completed", True, job_orchestrator_pb2.SUCCEEDED, True),
        ("failed", True, job_orchestrator_pb2.FAILED_FINAL, True),
        ("failed", False, job_orchestrator_pb2.RETRYING, False),
    ],
)
async def test_get_job_status_maps_snapshot_to_proto(
    grpc_orchestrator_stub: tuple[
        job_orchestrator_pb2_grpc.JobOrchestratorStub,
        list[tuple[str, bytes]],
        dict[str, _StatusSubscription],
        dict[str, dict[str, object]],
    ],
    status: str,
    is_terminal: bool,
    expected_state: int,
    expected_terminal: bool,
) -> None:
    stub, _, _, snapshots = grpc_orchestrator_stub
    job_id = str(uuid4())
    snapshots[job_id] = {
        "job_id": job_id,
        "status": status,
        "attempt": 2,
        "last_error": "boom" if status == "failed" else None,
        "is_terminal": is_terminal,
        "updated_at": "2026-01-01T00:00:00+00:00",
    }

    reply = await stub.GetJobStatus(job_orchestrator_pb2.GetJobStatusRequest(job_id=job_id))

    assert reply.job_id == job_id
    assert reply.state == expected_state
    assert reply.terminal is expected_terminal
    assert reply.attempt == 2


@pytest.mark.asyncio
async def test_get_job_status_returns_not_found_for_unknown_job(
    grpc_orchestrator_stub: tuple[
        job_orchestrator_pb2_grpc.JobOrchestratorStub,
        list[tuple[str, bytes]],
        dict[str, _StatusSubscription],
        dict[str, dict[str, object]],
    ]
) -> None:
    stub, _, _, _ = grpc_orchestrator_stub

    with pytest.raises(grpc.aio.AioRpcError) as error:
        await stub.GetJobStatus(job_orchestrator_pb2.GetJobStatusRequest(job_id=str(uuid4())))

    assert error.value.code() == grpc.StatusCode.NOT_FOUND


@pytest.mark.asyncio
async def test_get_job_status_rejects_invalid_job_id(
    grpc_orchestrator_stub: tuple[
        job_orchestrator_pb2_grpc.JobOrchestratorStub,
        list[tuple[str, bytes]],
        dict[str, _StatusSubscription],
        dict[str, dict[str, object]],
    ]
) -> None:
    stub, _, _, _ = grpc_orchestrator_stub

    with pytest.raises(grpc.aio.AioRpcError) as error:
        await stub.GetJobStatus(job_orchestrator_pb2.GetJobStatusRequest(job_id="not-a-uuid"))

    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT
