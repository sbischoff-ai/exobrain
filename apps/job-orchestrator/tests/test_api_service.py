from __future__ import annotations

import json

import grpc
import pytest

from app.transport.grpc import job_orchestrator_pb2
from app.transport.grpc.service import JobOrchestratorServicer


class FakeContext:
    async def abort(self, *, code: grpc.StatusCode, details: str):
        raise RuntimeError(f"{code.name}:{details}")


@pytest.mark.asyncio
async def test_enqueue_job_publishes_knowledge_update_payload() -> None:
    published: list[tuple[str, bytes]] = []

    async def publish(subject: str, payload: bytes) -> None:
        published.append((subject, payload))

    servicer = JobOrchestratorServicer(publish)
    request = job_orchestrator_pb2.EnqueueJobRequest(
        job_type="knowledge.update",
        user_id="user-1",
        knowledge_update=job_orchestrator_pb2.KnowledgeUpdatePayload(
            journal_reference="2026/02/24",
            requested_by_user_id="user-1",
            messages=[job_orchestrator_pb2.KnowledgeUpdateMessage(role="user", content="hello")],
        ),
    )

    reply = await servicer.EnqueueJob(request, FakeContext())

    assert reply.job_id
    assert len(published) == 1
    subject, envelope = published[0]
    assert subject == "jobs.knowledge.update.requested"
    decoded = json.loads(envelope)
    assert decoded["correlation_id"] == "user-1"
    assert decoded["payload"]["requested_by_user_id"] == "user-1"


@pytest.mark.asyncio
async def test_enqueue_job_rejects_missing_typed_payload_for_knowledge_update() -> None:
    async def publish(_: str, __: bytes) -> None:
        return None

    servicer = JobOrchestratorServicer(publish)
    request = job_orchestrator_pb2.EnqueueJobRequest(job_type="knowledge.update", user_id="user-1")

    with pytest.raises(RuntimeError) as exc_info:
        await servicer.EnqueueJob(request, FakeContext())

    assert "INVALID_ARGUMENT" in str(exc_info.value)
    assert "knowledge_update payload is required" in str(exc_info.value)
