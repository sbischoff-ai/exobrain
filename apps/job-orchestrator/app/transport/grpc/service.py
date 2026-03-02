from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import UUID, uuid4

import grpc
from pydantic import ValidationError

from app.contracts import JobEnvelope, JobStatusEvent
from app.transport.grpc import job_orchestrator_pb2, job_orchestrator_pb2_grpc
from app.worker.job_registry import JOB_PAYLOAD_MODEL_BY_TYPE


def _job_id_subject(job_id: str) -> str:
    return f"jobs.status.{job_id}"


def _to_lifecycle_state(state: str, is_terminal: bool) -> job_orchestrator_pb2.JobLifecycleState:
    normalized = state.lower()
    if normalized in {"requested", "pending", "enqueued_or_pending"}:
        return job_orchestrator_pb2.ENQUEUED_OR_PENDING
    if normalized in {"processing", "started"}:
        return job_orchestrator_pb2.STARTED
    if normalized == "retrying":
        return job_orchestrator_pb2.RETRYING
    if normalized in {"completed", "succeeded"}:
        return job_orchestrator_pb2.SUCCEEDED
    if normalized == "failed" and is_terminal:
        return job_orchestrator_pb2.FAILED_FINAL
    if normalized == "failed":
        return job_orchestrator_pb2.RETRYING
    raise ValueError(f"unsupported lifecycle state: {state}")


class JobOrchestratorServicer(job_orchestrator_pb2_grpc.JobOrchestratorServicer):
    def __init__(
        self,
        publish_job: Callable[[str, bytes], Awaitable[None]],
        *,
        fetch_job_status: Callable[[str], Awaitable[dict[str, Any] | None]] | None = None,
        subscribe_job_status: Callable[[str], Awaitable[AsyncIterator[bytes]]] | None = None,
    ) -> None:
        self._publish_job = publish_job
        self._fetch_job_status = fetch_job_status
        self._subscribe_job_status = subscribe_job_status

    async def EnqueueJob(
        self,
        request: job_orchestrator_pb2.EnqueueJobRequest,
        context,
    ) -> job_orchestrator_pb2.EnqueueJobReply:
        if not request.job_type:
            await context.abort(code=grpc.StatusCode.INVALID_ARGUMENT, details="job_type is required")
        if not request.user_id:
            await context.abort(code=grpc.StatusCode.INVALID_ARGUMENT, details="user_id is required")
        if request.job_type not in JOB_PAYLOAD_MODEL_BY_TYPE:
            await context.abort(code=grpc.StatusCode.INVALID_ARGUMENT, details=f"unsupported job_type: {request.job_type}")

        try:
            payload = self._resolve_payload(request)
            payload_model = JOB_PAYLOAD_MODEL_BY_TYPE[request.job_type]
            validated_payload = payload_model.model_validate(payload).model_dump(mode="json")
        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            await context.abort(code=grpc.StatusCode.INVALID_ARGUMENT, details=str(exc))

        job_id = str(uuid4())
        job = JobEnvelope(
            schema_version=1,
            job_id=job_id,
            job_type=request.job_type,
            correlation_id=request.user_id,
            payload=validated_payload,
            attempt=0,
            created_at=datetime.now(timezone.utc),
        )
        subject = f"jobs.{job.job_type}.requested"
        await self._publish_job(subject, job.model_dump_json().encode("utf-8"))
        await self._publish_job(
            _job_id_subject(job_id),
            JobStatusEvent(job_id=job_id, state="ENQUEUED_OR_PENDING", attempt=0, terminal=False).model_dump_json().encode("utf-8"),
        )
        return job_orchestrator_pb2.EnqueueJobReply(job_id=job_id)

    async def GetJobStatus(
        self,
        request: job_orchestrator_pb2.GetJobStatusRequest,
        context,
    ) -> job_orchestrator_pb2.GetJobStatusReply:
        job_id = self._validate_job_id(request.job_id)
        if not job_id:
            await context.abort(code=grpc.StatusCode.INVALID_ARGUMENT, details="job_id must be a valid UUID")

        if self._fetch_job_status is None:
            await context.abort(code=grpc.StatusCode.UNIMPLEMENTED, details="status lookup is not configured")

        status = await self._fetch_job_status(job_id)
        if status is None:
            await context.abort(code=grpc.StatusCode.NOT_FOUND, details="job not found")

        return self._status_snapshot_to_reply(status)

    async def WatchJobStatus(
        self,
        request: job_orchestrator_pb2.WatchJobStatusRequest,
        context,
    ) -> AsyncIterator[job_orchestrator_pb2.JobStatusEvent]:
        job_id = self._validate_job_id(request.job_id)
        if not job_id:
            await context.abort(code=grpc.StatusCode.INVALID_ARGUMENT, details="job_id must be a valid UUID")

        if self._subscribe_job_status is None:
            await context.abort(code=grpc.StatusCode.UNIMPLEMENTED, details="status stream is not configured")

        if request.include_current:
            if self._fetch_job_status is None:
                await context.abort(code=grpc.StatusCode.UNIMPLEMENTED, details="status lookup is not configured")
            snapshot = await self._fetch_job_status(job_id)
            if snapshot is None:
                await context.abort(code=grpc.StatusCode.NOT_FOUND, details="job not found")
            current = self._status_snapshot_to_event(snapshot)
            yield current
            if current.terminal:
                return

        subscription = await self._subscribe_job_status(_job_id_subject(job_id))

        try:
            async for payload in subscription:
                if context.cancelled():
                    return
                event = JobStatusEvent.model_validate_json(payload.decode("utf-8"))
                if event.job_id != job_id:
                    continue
                response = self._job_status_event_to_proto(event)
                yield response
                if response.terminal:
                    return
        finally:
            unsubscribe = getattr(subscription, "unsubscribe", None)
            if callable(unsubscribe):
                maybe_awaitable = unsubscribe()
                if hasattr(maybe_awaitable, "__await__"):
                    await maybe_awaitable

    @staticmethod
    def _validate_job_id(job_id: str) -> str | None:
        if not job_id:
            return None
        try:
            UUID(job_id)
        except ValueError:
            return None
        return job_id

    @staticmethod
    def _status_snapshot_to_reply(status: dict[str, Any]) -> job_orchestrator_pb2.GetJobStatusReply:
        state = _to_lifecycle_state(status["status"], bool(status.get("is_terminal")))
        return job_orchestrator_pb2.GetJobStatusReply(
            job_id=status["job_id"],
            state=state,
            attempt=int(status.get("attempt") or 0),
            detail=status.get("last_error") or "",
            terminal=bool(status.get("is_terminal")),
            updated_at=JobOrchestratorServicer._format_timestamp(status.get("updated_at")),
        )

    @staticmethod
    def _status_snapshot_to_event(status: dict[str, Any]) -> job_orchestrator_pb2.JobStatusEvent:
        state = _to_lifecycle_state(status["status"], bool(status.get("is_terminal")))
        return job_orchestrator_pb2.JobStatusEvent(
            job_id=status["job_id"],
            state=state,
            attempt=int(status.get("attempt") or 0),
            detail=status.get("last_error") or "",
            terminal=bool(status.get("is_terminal")),
            emitted_at=JobOrchestratorServicer._format_timestamp(status.get("updated_at")),
        )

    @staticmethod
    def _job_status_event_to_proto(event: JobStatusEvent) -> job_orchestrator_pb2.JobStatusEvent:
        return job_orchestrator_pb2.JobStatusEvent(
            job_id=event.job_id,
            state=getattr(job_orchestrator_pb2, event.state),
            attempt=event.attempt,
            detail=event.detail or "",
            terminal=event.terminal,
            emitted_at=event.emitted_at.isoformat(),
        )

    @staticmethod
    def _format_timestamp(value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        if value is None:
            return ""
        return str(value)

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
