from __future__ import annotations

import asyncio
import logging

import nats

from app.database import Database
from app.job_repository import JobRepository
from app.orchestrator import JobOrchestrator
from app.settings import get_settings
from app.worker import LocalProcessWorkerRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()

    db = Database(settings.job_orchestrator_db_dsn, reshape_schema_query=settings.reshape_schema_query)
    await db.connect()

    nc = await nats.connect(settings.exobrain_nats_url)
    js = nc.jetstream()

    await js.add_stream(name="JOBS", subjects=["jobs.>"])

    repository = JobRepository(db)
    orchestrator = JobOrchestrator(
        repository=repository,
        runner=LocalProcessWorkerRunner(),
        events_subject_prefix=settings.job_events_subject_prefix,
        dlq_subject=settings.job_dlq_subject,
        max_attempts=settings.job_max_attempts,
        publish_event=js.publish,
    )
    concurrency_guard = asyncio.Semaphore(settings.worker_replica_count)

    async def handle(msg):
        async with concurrency_guard:
            await orchestrator.process_message(msg)

    await js.subscribe(
        settings.job_queue_subject,
        durable="job-orchestrator-worker",
        cb=handle,
        manual_ack=True,
    )
    logger.info(
        "job orchestrator worker started",
        extra={"subject": settings.job_queue_subject, "replicas": settings.worker_replica_count},
    )

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await nc.drain()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
