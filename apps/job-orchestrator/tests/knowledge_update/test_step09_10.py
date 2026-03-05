from __future__ import annotations

from app.contracts import KnowledgeUpdatePayload
from app.worker.jobs.knowledge_update import _build_step_nine_merge_graph_delta, _build_step_ten_mentions_schema
from app.worker.jobs.knowledge_update_types import EntityExtractionResult, FinalEntityContextGraph, MatchedRelationship


def test_step10_mentions_schema_requires_mentions() -> None:
    schema = _build_step_ten_mentions_schema()
    assert schema["required"] == ["mentions"]


def test_step09_merge_graph_delta_maps_blocks_edges_and_universes() -> None:
    payload = KnowledgeUpdatePayload(journal_reference="journal-1", requested_by_user_id="user-1", messages=[{"role": "user", "content": "hello", "created_at": "2026-03-02T12:00:00Z"}])
    merged = _build_step_nine_merge_graph_delta(
        payload=payload,
        step_zero_graph_delta={"entities": [], "blocks": [], "edges": [], "universes": []},
        step_two_extraction=EntityExtractionResult.model_validate({"extracted_entities": [], "extracted_universes": [{"name": "Wonderland", "description": "fictional"}]}),
        step_seven_relationships=[MatchedRelationship(from_entity_id="e1", to_entity_id="e2", edge_type="edge.related_to", confidence=0.8)],
        step_eight_final_entity_context_graphs=[FinalEntityContextGraph.model_validate({"entity": {"entity_id": "e1", "node_type": "node.person", "name": "Alice", "aliases": ["A"], "universe_name": "Wonderland"}, "blocks": [{"block_id": "NEW_BLOCK_1", "parent_block_id": "", "text": "root"}]})],
    )
    assert len(merged["universes"]) == 1
    assert len(merged["entities"]) == 1
