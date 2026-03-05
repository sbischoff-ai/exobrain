from __future__ import annotations

import grpc

from app.contracts import KnowledgeUpdatePayload
from app.worker.jobs.knowledge_update import core


async def run(channel: grpc.aio.Channel, payload: KnowledgeUpdatePayload) -> dict[str, object]:
    return await core._build_upsert_graph_delta_step_one(channel, payload)
