from __future__ import annotations

import asyncio
import logging

from app.database import Database
from app.job_repository import JobRepository
from app.jetstream import connect_jetstream, ensure_jobs_stream
from app.logging import configure_logging
from app.orchestrator import JobOrchestrator
from app.settings import get_settings
from app.worker import LocalProcessWorkerRunner

settings = get_settings()
configure_logging(settings.effective_log_level)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("starting job orchestrator", extra={"app_env": settings.app_env, "log_level": settings.effective_log_level})

    db = Database(settings.job_orchestrator_db_dsn, reshape_schema_query=settings.reshape_schema_query)
    await db.connect()
    logger.info("job orchestrator database connected")

    nc, js = await connect_jetstream(settings.exobrain_nats_url)
    logger.info("job orchestrator nats connected", extra={"nats_url": settings.exobrain_nats_url})

    await ensure_jobs_stream(js)

    repository = JobRepository(db)
    orchestrator = JobOrchestrator(
        repository=repository,
        runner=LocalProcessWorkerRunner(),
        events_subject_prefix=settings.job_events_subject_prefix,
        dlq_subject=settings.job_dlq_subject,
        max_attempts=settings.job_max_attempts,
        dlq_raw_message_max_chars=settings.job_dlq_raw_message_max_chars,
        publish_event=js.publish,
    )
    concurrency_guard = asyncio.Semaphore(settings.worker_replica_count)

    async def handle(msg):
        logger.debug("received job message", extra={"subject": msg.subject})
        async with concurrency_guard:
            await orchestrator.process_message(msg)

    await js.subscribe(
        settings.job_queue_subject,
        durable=settings.job_consumer_durable,
        cb=handle,
        manual_ack=True,
    )
    logger.info(
        "job orchestrator worker started",
        extra={"subject": settings.job_queue_subject, "replicas": settings.worker_replica_count, "durable": settings.job_consumer_durable},
    )

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await nc.drain()
        await db.close()
        logger.info("job orchestrator shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
