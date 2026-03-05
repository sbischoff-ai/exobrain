from __future__ import annotations

from app.contracts import KnowledgeUpdatePayload
from app.worker.jobs.knowledge_update import core
from app.worker.jobs.knowledge_update.types import EntityExtractionResult, FinalEntityContextGraph, MatchedRelationship


def run(
    payload: KnowledgeUpdatePayload,
    step_zero_graph_delta: dict[str, object],
    step_two_extraction: EntityExtractionResult,
    step_seven_relationships: list[MatchedRelationship],
    step_eight_final_entity_context_graphs: list[FinalEntityContextGraph],
) -> dict[str, object]:
    return core._build_step_nine_merge_graph_delta(
        payload,
        step_zero_graph_delta,
        step_two_extraction,
        step_seven_relationships,
        step_eight_final_entity_context_graphs,
    )
