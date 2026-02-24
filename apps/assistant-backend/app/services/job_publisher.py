from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import nats
from nats.js import JetStreamContext

from app.services.contracts import JobPublisherProtocol


class NatsJobPublisher(JobPublisherProtocol):
    """NATS/JetStream-backed publisher for asynchronous jobs."""

    def __init__(self, nats_url: str, subject_prefix: str) -> None:
        self._nats_url = nats_url
        self._subject_prefix = subject_prefix
        self._connection: nats.NATS | None = None
        self._jetstream: JetStreamContext | None = None

    async def connect(self) -> None:
        if self._connection is not None:
            return
        self._connection = await nats.connect(self._nats_url)
        self._jetstream = self._connection.jetstream()
        await self._jetstream.add_stream(name="JOBS", subjects=[f"{self._subject_prefix}.>"])

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.drain()
            self._connection = None
            self._jetstream = None

    async def enqueue_job(self, *, job_type: str, correlation_id: str, payload: dict[str, object]) -> str:
        if self._jetstream is None:
            raise RuntimeError("job publisher is not connected")

        job_id = str(uuid4())
        subject = f"{self._subject_prefix}.{job_type}.requested"
        envelope = {
            "schema_version": 1,
            "job_id": job_id,
            "job_type": job_type,
            "correlation_id": correlation_id,
            "payload": payload,
            "attempt": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._jetstream.publish(subject, json.dumps(envelope).encode("utf-8"))
        return job_id
