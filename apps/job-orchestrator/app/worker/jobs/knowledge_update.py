from __future__ import annotations

import argparse
import asyncio

import grpc

from app.contracts import JobEnvelope
from app.settings import get_settings


async def run(job: JobEnvelope) -> None:
    """Skeleton knowledge-update worker: verify connectivity to knowledge interface."""

    settings = get_settings()
    async with grpc.aio.insecure_channel(settings.knowledge_interface_grpc_target) as channel:
        await asyncio.wait_for(channel.channel_ready(), timeout=settings.knowledge_interface_connect_timeout_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run knowledge.update worker job")
    parser.add_argument("--job-envelope", required=True, help="Serialized JobEnvelope JSON payload")
    args = parser.parse_args()

    job = JobEnvelope.model_validate_json(args.job_envelope)
    asyncio.run(run(job))


if __name__ == "__main__":
    main()
