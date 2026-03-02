from __future__ import annotations

import json
from uuid import UUID

import grpc
import pytest
from pydantic import BaseModel

from app.contracts import JobEnvelope
from app.transport.grpc import job_orchestrator_pb2, job_orchestrator_pb2_grpc
from app.transport.grpc.service import JobOrchestratorServicer
from app.worker.job_registry import JOB_PAYLOAD_MODEL_BY_TYPE


@pytest.fixture
async def grpc_orchestrator_stub() -> tuple[job_orchestrator_pb2_grpc.JobOrchestratorStub, list[tuple[str, bytes]]]:
    published: list[tuple[str, bytes]] = []

    async def publish(subject: str, payload: bytes) -> None:
        published.append((subject, payload))

    server = grpc.aio.server()
    job_orchestrator_pb2_grpc.add_JobOrchestratorServicer_to_server(JobOrchestratorServicer(publish), server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()

    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    stub = job_orchestrator_pb2_grpc.JobOrchestratorStub(channel)

    try:
        yield stub, published
    finally:
        await channel.close()
        await server.stop(grace=None)


@pytest.mark.asyncio
async def test_enqueue_job_success_publishes_expected_subject_and_job_id(
    grpc_orchestrator_stub: tuple[job_orchestrator_pb2_grpc.JobOrchestratorStub, list[tuple[str, bytes]]]
) -> None:
    stub, published = grpc_orchestrator_stub

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
    assert len(published) == 1
    subject, _ = published[0]
    assert subject == "jobs.knowledge.update.requested"


@pytest.mark.asyncio
async def test_enqueue_job_invalid_payload_or_job_type_returns_grpc_error(
    grpc_orchestrator_stub: tuple[job_orchestrator_pb2_grpc.JobOrchestratorStub, list[tuple[str, bytes]]]
) -> None:
    stub, _ = grpc_orchestrator_stub

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
    grpc_orchestrator_stub: tuple[job_orchestrator_pb2_grpc.JobOrchestratorStub, list[tuple[str, bytes]]]
) -> None:
    stub, published = grpc_orchestrator_stub

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
