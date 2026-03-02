from __future__ import annotations

import json
from typing import Awaitable, Callable

from app.contracts import JobEnvelope
import grpc
from app.transport.grpc import job_orchestrator_pb2, job_orchestrator_pb2_grpc


class JobOrchestratorServicer(job_orchestrator_pb2_grpc.JobOrchestratorServicer):
    def __init__(self, publish_job: Callable[[str, bytes], Awaitable[None]]) -> None:
        self._publish_job = publish_job

    async def EnqueueJob(
        self,
        request: job_orchestrator_pb2.EnqueueJobRequest,
        context,
    ) -> job_orchestrator_pb2.EnqueueJobReply:
        if not request.job_type:
            await context.abort(code=grpc.StatusCode.INVALID_ARGUMENT, details="job_type is required")
        if not request.user_id:
            await context.abort(code=grpc.StatusCode.INVALID_ARGUMENT, details="user_id is required")

        try:
            payload = self._resolve_payload(request)
        except (ValueError, json.JSONDecodeError) as exc:
            await context.abort(code=grpc.StatusCode.INVALID_ARGUMENT, details=str(exc))
        job = JobEnvelope(job_type=request.job_type, correlation_id=request.user_id, payload=payload)
        subject = f"jobs.{job.job_type}.requested"
        await self._publish_job(subject, job.model_dump_json().encode("utf-8"))
        return job_orchestrator_pb2.EnqueueJobReply(job_id=job.job_id)

    @staticmethod
    def _resolve_payload(request: job_orchestrator_pb2.EnqueueJobRequest) -> dict[str, object]:
        payload_case = request.WhichOneof("payload")

        if request.job_type == "knowledge.update":
            if payload_case != "knowledge_update":
                raise ValueError("knowledge_update payload is required for knowledge.update jobs")
            typed = request.knowledge_update
            messages = []
            for message in typed.messages:
                messages.append(
                    {
                        "role": message.role,
                        "content": message.content or None,
                        "sequence": message.sequence or None,
                        "created_at": message.created_at or None,
                    }
                )
            return {
                "journal_reference": typed.journal_reference,
                "messages": messages,
                "requested_by_user_id": typed.requested_by_user_id,
            }

        if payload_case == "payload_json":
            decoded = json.loads(request.payload_json)
            if not isinstance(decoded, dict):
                raise ValueError("payload_json must decode to an object")
            return decoded

        raise ValueError("payload_json is required for non-knowledge.update jobs")
