from __future__ import annotations

from app.worker.jobs.knowledge_update import (
    _assert_step_eight_required_entity_fields,
    _build_edge_extraction_schema_context_request,
    _build_step_eight_final_entity_context_graph_schema,
    _build_step_seven_relationship_match_schema,
    _build_step_six_relationship_extraction_schema,
    _deduplicate_entity_pairs,
)
from app.worker.jobs.knowledge_update.core import _normalize_step_eight_structured_response
from app.worker.jobs.knowledge_update_types import RelationshipPair
from app.worker.jobs.knowledge_update_types import ExtractedEntity, ResolvedEntity


def test_step06_schema_and_dedupe() -> None:
    schema = _build_step_six_relationship_extraction_schema()
    assert schema["required"] == ["entity_pairs"]
    pairs = _deduplicate_entity_pairs([RelationshipPair(entity_id_1="a", entity_id_2="b"), RelationshipPair(entity_id_1="b", entity_id_2="a")], {"a", "b"})
    assert pairs == [RelationshipPair(entity_id_1="a", entity_id_2="b")]


def test_step07_and_step08_schema_requirements() -> None:
    assert _build_step_seven_relationship_match_schema()["required"] == ["from_entity_id", "to_entity_id", "edge_type", "confidence"]
    schema = _build_step_eight_final_entity_context_graph_schema()
    assert schema["required"] == ["entity", "blocks"]
    assert schema["properties"]["entity"]["required"] == ["entity_id", "node_type", "name", "aliases"]
    assert schema["properties"]["blocks"]["items"]["required"] == ["block_id", "text"]
    assert schema["properties"]["blocks"]["items"]["properties"]["text"]["minLength"] == 1


def test_step07_edge_context_request_uses_current_proto_fields() -> None:
    request = _build_edge_extraction_schema_context_request("person", "company", "user-1")

    assert request.user_id == "user-1"
    assert request.first_entity_type == "person"
    assert request.second_entity_type == "company"


def test_step08_normalizes_only_allowed_entity_fields() -> None:
    resolved = ResolvedEntity(
        entity_index=0,
        extracted_entity=ExtractedEntity(
            name="Octavia Butler",
            node_type="node.person",
            aliases=["OEB"],
            short_description="science fiction author",
            universe_id=None,
        ),
        resolved_entity_id="entity-1",
        resolution_status="matched",
    )

    normalized = _normalize_step_eight_structured_response(
        {
            "entity": {
                "entity_id": "entity-1",
                "node_type": "node.person",
                "name": "Octavia Butler",
                "aliases": ["OEB"],
                "short_description": "science fiction author",
            },
            "blocks": [{"block_id": "NEW_BLOCK_1", "text": "root"}],
        },
        resolved,
        writable_property_keys={"name", "aliases"},
    )

    assert normalized["entity"] == {
        "entity_id": "entity-1",
        "node_type": "node.person",
        "name": "Octavia Butler",
        "aliases": ["OEB"],
    }


def test_step08_removes_non_writable_entity_keys() -> None:
    resolved = ResolvedEntity(
        entity_index=0,
        extracted_entity=ExtractedEntity(
            name="Octavia Butler",
            node_type="node.person",
            aliases=["OEB"],
            short_description="science fiction author",
            universe_id="univ-1",
        ),
        resolved_entity_id="entity-1",
        resolution_status="matched",
    )

    normalized = _normalize_step_eight_structured_response(
        {
            "entity": {
                "entity_id": "entity-1",
                "node_type": "node.person",
                "name": "Octavia Butler",
                "aliases": ["OEB"],
                "favorite_color": "purple",
            },
            "blocks": [{"block_id": "NEW_BLOCK_1", "text": "root"}],
        },
        resolved,
        writable_property_keys={"name", "aliases"},
    )

    assert normalized["entity"] == {
        "entity_id": "entity-1",
        "node_type": "node.person",
        "name": "Octavia Butler",
        "aliases": ["OEB"],
        "universe_id": "univ-1",
    }


def test_step08_rejects_missing_required_entity_keys_after_normalization() -> None:
    malformed = {
        "entity": {
            "entity_id": "entity-1",
            "aliases": ["OEB"],
        },
        "blocks": [{"block_id": "NEW_BLOCK_1", "text": "root"}],
    }

    try:
        _assert_step_eight_required_entity_fields(malformed, "entity-1")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "missing required entity keys" in str(exc)
        assert "node_type" in str(exc)
        assert "name" in str(exc)


def test_step08_rejects_missing_entity_payload_after_normalization() -> None:
    malformed = {"blocks": [{"block_id": "NEW_BLOCK_1", "text": "root"}]}

    try:
        _assert_step_eight_required_entity_fields(malformed, "entity-1")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "missing required entity keys" in str(exc)
