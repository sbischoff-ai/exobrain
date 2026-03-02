from __future__ import annotations

import asyncio
import logging
import signal

import grpc
import nats

from app.logging import configure_logging
from app.settings import get_settings
from app.transport.grpc import job_orchestrator_pb2_grpc
from app.transport.grpc.service import JobOrchestratorServicer

settings = get_settings()
configure_logging(settings.effective_log_level)
logger = logging.getLogger(__name__)


async def main() -> None:
    nc = await nats.connect(settings.exobrain_nats_url)
    js = nc.jetstream()
    await js.add_stream(name="JOBS", subjects=["jobs.>"])

    server = grpc.aio.server()
    servicer = JobOrchestratorServicer(js.publish)
    job_orchestrator_pb2_grpc.add_JobOrchestratorServicer_to_server(servicer, server)

    bind_target = f"{settings.job_orchestrator_api_host}:{settings.job_orchestrator_api_port}"
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
        logger.info("job orchestrator api shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
