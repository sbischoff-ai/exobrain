from __future__ import annotations

import asyncio
import logging
import signal

import grpc
from app.database import Database
from nats.aio.subscription import Subscription
from app.jetstream import connect_jetstream, ensure_jobs_stream
from app.job_repository import JobRepository
from app.logging import configure_logging
from app.settings import get_settings
from app.transport.grpc import job_orchestrator_pb2_grpc
from app.transport.grpc.service import JobOrchestratorServicer

settings = get_settings()
configure_logging(settings.effective_log_level)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not settings.job_orchestrator_api_enabled:
        logger.info("job orchestrator api disabled via config")
        return

    db = Database(settings.job_orchestrator_db_dsn, reshape_schema_query=settings.reshape_schema_query)
    await db.connect()

    nc, js = await connect_jetstream(settings.exobrain_nats_url)
    await ensure_jobs_stream(js)
    repository = JobRepository(db)

    async def fetch_status(job_id: str):
        return await repository.get_status(job_id)

    async def subscribe_status(subject: str):
        sub: Subscription = await js.subscribe(subject)

        async def _messages():
            async for msg in sub.messages:
                yield msg.data

        class _Wrapper:
            def __aiter__(self):
                return _messages()

            async def unsubscribe(self):
                await sub.unsubscribe()

        return _Wrapper()

    server = grpc.aio.server()
    servicer = JobOrchestratorServicer(js.publish, fetch_job_status=fetch_status, subscribe_job_status=subscribe_status)
    job_orchestrator_pb2_grpc.add_JobOrchestratorServicer_to_server(servicer, server)

    bind_target = settings.job_orchestrator_api_bind_target
    server.add_insecure_port(bind_target)
    await server.start()
    logger.info("job orchestrator api started", extra={"bind_target": bind_target})

    stop_event = asyncio.Event()

    def request_shutdown() -> None:
        if not stop_event.is_set():
            stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_shutdown)
        except NotImplementedError:
            pass

    try:
        await stop_event.wait()
    finally:
        await server.stop(grace=5)
        await nc.drain()
        await db.close()
        logger.info("job orchestrator api shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
