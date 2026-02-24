from __future__ import annotations

import argparse
import asyncio

from grpclib.client import Channel

from app.contracts import JobEnvelope
from app.settings import get_settings


def _parse_target(target: str) -> tuple[str, int]:
    host, sep, port = target.rpartition(":")
    if sep == "" or not host or not port:
        raise ValueError(f"invalid KNOWLEDGE_INTERFACE_GRPC_TARGET '{target}', expected host:port")
    return host, int(port)


async def run(job: JobEnvelope) -> None:
    """Skeleton knowledge-update worker: verify connectivity to knowledge interface."""

    settings = get_settings()
    host, port = _parse_target(settings.knowledge_interface_grpc_target)
    channel = Channel(host=host, port=port)
    try:
        await asyncio.wait_for(channel.__connect__(), timeout=settings.knowledge_interface_connect_timeout_seconds)
    finally:
        channel.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run knowledge.update worker job")
    parser.add_argument("--job-envelope", required=True, help="Serialized JobEnvelope JSON payload")
    args = parser.parse_args()

    job = JobEnvelope.model_validate_json(args.job_envelope)
    asyncio.run(run(job))


if __name__ == "__main__":
    main()
