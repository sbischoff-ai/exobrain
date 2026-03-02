from __future__ import annotations

import json

import grpc

from app.services.contracts import JobPublisherProtocol
from app.services.grpc import job_orchestrator_pb2, job_orchestrator_pb2_grpc


class JobOrchestratorClient(JobPublisherProtocol):
    """gRPC client for the job-orchestrator EnqueueJob endpoint."""

    def __init__(self, grpc_target: str) -> None:
        self._grpc_target = grpc_target
        self._channel: grpc.aio.Channel | None = None
        self._stub: job_orchestrator_pb2_grpc.JobOrchestratorStub | None = None

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
            self._stub = None

    async def enqueue_job(self, *, job_type: str, payload: dict[str, object]) -> str:
        stub = self._get_or_create_stub()
        request = self._build_request(job_type=job_type, payload=payload)
        response = await stub.EnqueueJob(request)
        return response.job_id

    def _get_or_create_stub(self) -> job_orchestrator_pb2_grpc.JobOrchestratorStub:
        if self._stub is None:
            self._channel = grpc.aio.insecure_channel(self._grpc_target)
            self._stub = job_orchestrator_pb2_grpc.JobOrchestratorStub(self._channel)
        return self._stub

    @staticmethod
    def _build_request(*, job_type: str, payload: dict[str, object]) -> job_orchestrator_pb2.EnqueueJobRequest:
        return job_orchestrator_pb2.EnqueueJobRequest(
            job_type=job_type,
            payload_json=json.dumps(payload),
        )
