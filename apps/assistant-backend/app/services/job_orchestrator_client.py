from __future__ import annotations

import json
from collections.abc import AsyncIterator

import grpc

from app.services.contracts import JobPublisherProtocol
from app.services.grpc import job_orchestrator_pb2, job_orchestrator_pb2_grpc


class JobOrchestratorClient(JobPublisherProtocol):
    """gRPC client for the job-orchestrator EnqueueJob endpoint."""

    def __init__(self, grpc_target: str, connect_timeout_seconds: float = 5.0) -> None:
        self._grpc_target = grpc_target
        self._connect_timeout_seconds = connect_timeout_seconds
        self._channel: grpc.aio.Channel | None = None
        self._stub: job_orchestrator_pb2_grpc.JobOrchestratorStub | None = None

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
            self._stub = None

    async def enqueue_job(self, *, user_id: str, job_type: str, payload: dict[str, object]) -> str:
        stub = self._get_or_create_stub()
        request = self._build_request(user_id=user_id, job_type=job_type, payload=payload)
        response = await stub.EnqueueJob(request, timeout=self._connect_timeout_seconds)
        return response.job_id


    async def get_job_status(self, *, job_id: str) -> job_orchestrator_pb2.GetJobStatusReply:
        stub = self._get_or_create_stub()
        request = job_orchestrator_pb2.GetJobStatusRequest(job_id=job_id)
        return await stub.GetJobStatus(request, timeout=self._connect_timeout_seconds)

    async def watch_job_status(self, *, job_id: str, include_current: bool = True) -> AsyncIterator[job_orchestrator_pb2.JobStatusEvent]:
        stub = self._get_or_create_stub()
        request = job_orchestrator_pb2.WatchJobStatusRequest(job_id=job_id, include_current=include_current)
        stream = stub.WatchJobStatus(request, timeout=self._connect_timeout_seconds)
        async for event in stream:
            yield event

    def _get_or_create_stub(self) -> job_orchestrator_pb2_grpc.JobOrchestratorStub:
        if self._stub is None:
            self._channel = grpc.aio.insecure_channel(self._grpc_target)
            self._stub = job_orchestrator_pb2_grpc.JobOrchestratorStub(self._channel)
        return self._stub

    @staticmethod
    def _build_request(*, user_id: str, job_type: str, payload: dict[str, object]) -> job_orchestrator_pb2.EnqueueJobRequest:
        if job_type == "knowledge.update":
            messages = [
                job_orchestrator_pb2.KnowledgeUpdateMessage(
                    role=str(message.get("role") or ""),
                    content=str(message.get("content") or ""),
                    sequence=int(message.get("sequence") or 0),
                    created_at=str(message.get("created_at") or ""),
                )
                for message in payload.get("messages", [])
                if isinstance(message, dict)
            ]
            return job_orchestrator_pb2.EnqueueJobRequest(
                job_type=job_type,
                user_id=user_id,
                knowledge_update=job_orchestrator_pb2.KnowledgeUpdatePayload(
                    journal_reference=str(payload.get("journal_reference") or ""),
                    requested_by_user_id=str(payload.get("requested_by_user_id") or user_id),
                    messages=messages,
                ),
            )

        return job_orchestrator_pb2.EnqueueJobRequest(
            job_type=job_type,
            user_id=user_id,
            payload_json=json.dumps(payload),
        )
