from __future__ import annotations

import grpc

from app.contracts import KnowledgeUpdatePayload
from app.settings import Settings
from app.worker.jobs.knowledge_update import core
from app.worker.jobs.knowledge_update.types import FinalEntityContextGraph, ResolvedEntity


def build_json_schema() -> dict[str, object]:
    return core._build_step_eight_final_entity_context_graph_schema()


async def run(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
    resolved_entities: list[ResolvedEntity],
    entity_context_documents: list[str],
    settings: Settings,
) -> list[FinalEntityContextGraph]:
    return await core._run_step_eight_build_final_entity_context_graphs(
        channel,
        payload,
        resolved_entities,
        entity_context_documents,
        settings,
    )
