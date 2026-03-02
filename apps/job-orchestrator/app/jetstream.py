from __future__ import annotations

from typing import Any

import nats


async def connect_jetstream(nats_url: str) -> tuple[Any, Any]:
    nc = await nats.connect(nats_url)
    return nc, nc.jetstream()


async def ensure_jobs_stream(js: Any) -> None:
    await js.add_stream(name="JOBS", subjects=["jobs.>"])
