from __future__ import annotations

import logging
from typing import Awaitable, Callable

from nats.aio.msg import Msg

from app.contracts import JobEnvelope, JobResultEvent, WorkerJobRunnerProtocol
from app.job_repository import JobRepository

logger = logging.getLogger(__name__)


class JobOrchestrator:
    def __init__(
        self,
        *,
        repository: JobRepository,
        runner: WorkerJobRunnerProtocol,
        events_subject_prefix: str,
        publish_event: Callable[[str, bytes], Awaitable[None]],
    ) -> None:
        self._repository = repository
        self._runner = runner
        self._events_subject_prefix = events_subject_prefix
        self._publish_event = publish_event

    async def process_message(self, msg: Msg) -> None:
        job = JobEnvelope.model_validate_json(msg.data)

        inserted = await self._repository.register_requested(job)
        if not inserted:
            logger.info("skipping duplicate job", extra={"job_id": job.job_id})
            await msg.ack()
            return

        await self._repository.mark_processing(job.job_id, job.attempt + 1)

        try:
            await self._runner.run_job(job)
            await self._repository.mark_completed(job.job_id)
            await self._emit_result(job, "completed")
            await msg.ack()
        except Exception as exc:  # noqa: BLE001
            logger.exception("job processing failed", extra={"job_id": job.job_id})
            await self._repository.mark_failed(job.job_id, str(exc))
            await self._emit_result(job, "failed", detail=str(exc))
            await msg.ack()

    async def _emit_result(self, job: JobEnvelope, status: str, detail: str | None = None) -> None:
        event = JobResultEvent(
            job_id=job.job_id,
            job_type=job.job_type,
            status=status,
            correlation_id=job.correlation_id,
            attempt=job.attempt + 1,
            detail=detail,
        )
        subject = f"{self._events_subject_prefix}.{job.job_type}.{status}"
        await self._publish_event(subject, event.model_dump_json().encode("utf-8"))
