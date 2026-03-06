from __future__ import annotations

from app.worker.jobs.knowledge_update import (
    _build_edge_extraction_schema_context_request,
    _edge_extraction_schema_context_to_dict,
    _build_step_eight_final_entity_context_graph_schema,
    _build_step_seven_relationship_match_schema,
    _build_step_six_relationship_extraction_schema,
    _deduplicate_entity_pairs,
)
from app.worker.jobs.knowledge_update_types import RelationshipPair


def test_step06_schema_and_dedupe() -> None:
    schema = _build_step_six_relationship_extraction_schema()
    assert schema["required"] == ["entity_pairs"]
    pairs = _deduplicate_entity_pairs([RelationshipPair(entity_id_1="a", entity_id_2="b"), RelationshipPair(entity_id_1="b", entity_id_2="a")], {"a", "b"})
    assert pairs == [RelationshipPair(entity_id_1="a", entity_id_2="b")]


def test_step07_and_step08_schema_requirements() -> None:
    assert _build_step_seven_relationship_match_schema()["required"] == ["from_entity_id", "to_entity_id", "edge_type", "confidence"]
    schema = _build_step_eight_final_entity_context_graph_schema()
    assert schema["required"] == ["entity", "blocks"]


def test_step07_edge_context_request_uses_available_proto_fields() -> None:
    request = _build_edge_extraction_schema_context_request("person", "company", "user-1")

    assert request.user_id == "user-1"
    assert request.source_entity_type_id == "person"
    assert request.target_entity_type_id == "company"


def test_step07_edge_context_to_dict_defaults_when_reply_is_none() -> None:
    context = _edge_extraction_schema_context_to_dict(
        None,
        first_entity_type="person",
        second_entity_type="company",
    )

    assert context == {
        "source_entity_type_id": "person",
        "target_entity_type_id": "company",
        "entity_types": [],
    }
