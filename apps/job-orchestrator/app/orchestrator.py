from __future__ import annotations

import logging
from typing import Awaitable, Callable

from nats.aio.msg import Msg
from pydantic import ValidationError

from app.contracts import DeadLetterEvent, JobEnvelope, JobResultEvent, WorkerJobRunnerProtocol
from app.job_repository import JobRepository
from app.worker.job_registry import JOB_PAYLOAD_MODEL_BY_TYPE

logger = logging.getLogger(__name__)


class JobOrchestrator:
    def __init__(
        self,
        *,
        repository: JobRepository,
        runner: WorkerJobRunnerProtocol,
        events_subject_prefix: str,
        dlq_subject: str,
        max_attempts: int,
        dlq_raw_message_max_chars: int,
        publish_event: Callable[[str, bytes], Awaitable[None]],
    ) -> None:
        self._repository = repository
        self._runner = runner
        self._events_subject_prefix = events_subject_prefix
        self._dlq_subject = dlq_subject
        self._max_attempts = max_attempts
        self._dlq_raw_message_max_chars = dlq_raw_message_max_chars
        self._publish_event = publish_event

    async def process_message(self, msg: Msg) -> None:
        delivery_attempt = self._delivery_attempt(msg)

        if not msg.subject.endswith(".requested"):
            logger.warning("ignoring non-request subject", extra={"subject": msg.subject})
            await msg.ack()
            return

        try:
            job = JobEnvelope.model_validate_json(msg.data)
        except ValidationError as exc:
            logger.error(
                "invalid job envelope",
                extra={"error": str(exc), "attempt": delivery_attempt, "max_attempts": self._max_attempts, "subject": msg.subject},
            )
            if delivery_attempt >= self._max_attempts:
                await self._emit_dlq(reason="invalid-envelope", detail=str(exc), raw_message=msg.data)
                await msg.ack()
                return

            await msg.nak()
            return

        payload_error = self._validate_payload(job)
        if payload_error is not None:
            logger.error(
                "invalid job payload schema, sending to DLQ",
                extra={"job_id": job.job_id, "job_type": job.job_type, "error": payload_error},
            )
            await self._emit_dlq(reason="invalid-payload", detail=payload_error, raw_message=msg.data)
            await msg.ack()
            return

        run_job = job.model_copy(update={"attempt": delivery_attempt - 1})
        logger.debug("validated job envelope", extra={"job_id": run_job.job_id, "job_type": run_job.job_type, "attempt": delivery_attempt})

        if delivery_attempt == 1:
            inserted = await self._repository.register_requested(run_job)
            if not inserted:
                logger.info("skipping duplicate job", extra={"job_id": run_job.job_id})
                await msg.ack()
                return

        await self._repository.mark_processing(run_job.job_id, delivery_attempt)

        try:
            logger.info("starting job execution", extra={"job_id": run_job.job_id, "job_type": run_job.job_type, "attempt": delivery_attempt})
            await self._runner.run_job(run_job)
            await self._repository.mark_completed(run_job.job_id)
            await self._emit_result(run_job, "completed", attempt=delivery_attempt)
            logger.info("job execution completed", extra={"job_id": run_job.job_id, "job_type": run_job.job_type, "attempt": delivery_attempt})
            await msg.ack()
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "job processing failed",
                extra={"job_id": run_job.job_id, "attempt": delivery_attempt, "max_attempts": self._max_attempts},
            )
            await self._repository.mark_failed(run_job.job_id, str(exc))

            if delivery_attempt >= self._max_attempts:
                logger.error("max retries reached, sending to DLQ", extra={"job_id": run_job.job_id})
                await self._emit_result(run_job, "failed", attempt=delivery_attempt, detail=str(exc))
                await self._emit_dlq(reason="max-attempts", detail=str(exc), raw_message=msg.data)
                await msg.ack()
                return

            logger.warning("retrying job", extra={"job_id": run_job.job_id, "next_attempt": delivery_attempt + 1})
            await msg.nak()

    @staticmethod
    def _delivery_attempt(msg: Msg) -> int:
        metadata = getattr(msg, "metadata", None)
        value = getattr(metadata, "num_delivered", None)
        return value if isinstance(value, int) and value > 0 else 1

    @staticmethod
    def _validate_payload(job: JobEnvelope) -> str | None:
        payload_model = JOB_PAYLOAD_MODEL_BY_TYPE.get(job.job_type)
        if payload_model is None:
            return None

        try:
            payload_model.model_validate(job.payload)
            return None
        except ValidationError as exc:
            return str(exc)

    async def _emit_result(self, job: JobEnvelope, status: str, attempt: int, detail: str | None = None) -> None:
        event = JobResultEvent(
            job_id=job.job_id,
            job_type=job.job_type,
            status=status,
            correlation_id=job.correlation_id,
            attempt=attempt,
            detail=detail,
        )
        subject = f"{self._events_subject_prefix}.{job.job_type}.{status}"
        await self._publish_event(subject, event.model_dump_json().encode("utf-8"))

    async def _emit_dlq(self, *, reason: str, detail: str, raw_message: bytes) -> None:
        clipped_raw = raw_message.decode("utf-8", errors="replace")[: self._dlq_raw_message_max_chars]
        event = DeadLetterEvent(
            reason=reason,
            detail=detail,
            raw_message=clipped_raw,
        )
        try:
            await self._publish_event(self._dlq_subject, event.model_dump_json().encode("utf-8"))
        except Exception:
            logger.exception("failed to publish dlq event", extra={"reason": reason})
