from __future__ import annotations

from app.settings import Settings
from app.worker.jobs.knowledge_update import core
from app.worker.jobs.knowledge_update.types import RelationshipPair, ResolvedEntity


def build_json_schema() -> dict[str, object]:
    return core._build_step_six_relationship_extraction_schema()


def deduplicate_entity_pairs(entity_pairs: list[RelationshipPair], valid_entity_ids: set[str]) -> list[RelationshipPair]:
    return core._deduplicate_entity_pairs(entity_pairs, valid_entity_ids)


async def run(
    resolved_entities: list[ResolvedEntity], markdown_document: str, settings: Settings
) -> list[RelationshipPair]:
    return await core._run_step_six_relationship_extraction(resolved_entities, markdown_document, settings)
