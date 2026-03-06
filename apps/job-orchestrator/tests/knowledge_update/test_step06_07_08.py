from __future__ import annotations

from app.worker.jobs.knowledge_update import (
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


def test_step07_proto_contract_field_names() -> None:
    from app.services.grpc import knowledge_pb2

    request_fields = {field.name for field in knowledge_pb2.GetEdgeExtractionSchemaContextRequest.DESCRIPTOR.fields}
    reply_fields = {field.name for field in knowledge_pb2.GetEdgeExtractionSchemaContextReply.DESCRIPTOR.fields}

    assert {"first_entity_type", "second_entity_type", "user_id"}.issubset(request_fields)
    assert {"first_entity_type", "second_entity_type", "edge_types"}.issubset(reply_fields)
