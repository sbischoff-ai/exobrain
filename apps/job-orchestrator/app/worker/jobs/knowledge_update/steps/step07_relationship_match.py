from __future__ import annotations

import grpc

from app.contracts import KnowledgeUpdatePayload
from app.settings import Settings
from app.worker.jobs.knowledge_update import core
from app.worker.jobs.knowledge_update.types import MatchedRelationship, RelationshipPair, ResolvedEntity


def build_json_schema() -> dict[str, object]:
    return core._build_step_seven_relationship_match_schema()


async def run(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
    resolved_entities: list[ResolvedEntity],
    entity_context_documents: list[str],
    entity_pairs: list[RelationshipPair],
    settings: Settings,
) -> list[MatchedRelationship]:
    return await core._run_step_seven_match_relationship_type_and_score(
        channel,
        payload,
        resolved_entities,
        entity_context_documents,
        entity_pairs,
        settings,
    )
