from __future__ import annotations

import pytest
from uuid import UUID

from app.contracts import KnowledgeUpdatePayload
from app.worker.jobs.knowledge_update import (
    _build_step_nine_merge_graph_delta,
    _build_step_ten_mentions_schema,
    _preflight_validate_graph_delta_edges,
    _preflight_validate_graph_delta_entities,
)
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
        step_eight_final_entity_context_graphs=[FinalEntityContextGraph.model_validate({"entity": {"entity_id": "e1", "node_type": "node.person", "name": "Alice", "aliases": ["A"], "universe_name": "Wonderland"}, "blocks": [{"block_id": "arch-layers-001", "parent_block_id": "", "text": "root"}, {"block_id": "child-raw-id", "parent_block_id": "arch-layers-001", "text": "child"}]})],
    )
    assert len(merged["universes"]) == 1
    assert len(merged["entities"]) == 1

    blocks = [block for block in merged["blocks"] if isinstance(block, dict)]
    assert len(blocks) == 2
    for block in blocks:
        UUID(str(block["id"]))

    described_by_edges = [
        edge for edge in merged["edges"]
        if isinstance(edge, dict) and edge.get("edge_type") == "DESCRIBED_BY"
    ]
    assert len(described_by_edges) == 1
    UUID(str(described_by_edges[0]["to_id"]))

    summarizes_edges = [
        edge for edge in merged["edges"]
        if isinstance(edge, dict) and edge.get("edge_type") == "SUMMARIZES"
    ]
    assert len(summarizes_edges) == 1
    UUID(str(summarizes_edges[0]["from_id"]))
    UUID(str(summarizes_edges[0]["to_id"]))
    edges = merged["edges"]
    assert len(edges) == 3
    for edge in edges:
        props = {prop["key"]: prop for prop in edge["properties"]}
        assert "confidence" in props
        assert props["status"]["string_value"] == "asserted"
        assert props["provenance_hint"]["string_value"] == "placeholder"

    relationship_edge = next(edge for edge in edges if edge["edge_type"] == "edge.related_to")
    assert relationship_edge["properties"][0]["float_value"] == pytest.approx(0.8)


def test_step09_merge_graph_delta_rejects_multiple_roots() -> None:
    payload = KnowledgeUpdatePayload(journal_reference="journal-1", requested_by_user_id="user-1", messages=[{"role": "user", "content": "hello", "created_at": "2026-03-02T12:00:00Z"}])

    with pytest.raises(RuntimeError, match=r"entity_id=e1.*exactly one root block"):
        _build_step_nine_merge_graph_delta(
            payload=payload,
            step_zero_graph_delta={"entities": [], "blocks": [], "edges": [], "universes": []},
            step_two_extraction=EntityExtractionResult.model_validate({"extracted_entities": [], "extracted_universes": []}),
            step_seven_relationships=[],
            step_eight_final_entity_context_graphs=[
                FinalEntityContextGraph.model_validate(
                    {
                        "entity": {"entity_id": "e1", "node_type": "node.person", "name": "Alice"},
                        "blocks": [
                            {"block_id": "root-1", "parent_block_id": "", "text": "root-1"},
                            {"block_id": "root-2", "parent_block_id": "", "text": "root-2"},
                        ],
                    }
                )
            ],
        )


def test_step09_merge_graph_delta_rejects_dangling_parent_reference() -> None:
    payload = KnowledgeUpdatePayload(journal_reference="journal-1", requested_by_user_id="user-1", messages=[{"role": "user", "content": "hello", "created_at": "2026-03-02T12:00:00Z"}])

    with pytest.raises(RuntimeError, match=r"entity_id=e1.*dangling parent_block_id=missing-parent"):
        _build_step_nine_merge_graph_delta(
            payload=payload,
            step_zero_graph_delta={"entities": [], "blocks": [], "edges": [], "universes": []},
            step_two_extraction=EntityExtractionResult.model_validate({"extracted_entities": [], "extracted_universes": []}),
            step_seven_relationships=[],
            step_eight_final_entity_context_graphs=[
                FinalEntityContextGraph.model_validate(
                    {
                        "entity": {"entity_id": "e1", "node_type": "node.person", "name": "Alice"},
                        "blocks": [
                            {"block_id": "root-1", "parent_block_id": "", "text": "root"},
                            {"block_id": "child-1", "parent_block_id": "missing-parent", "text": "child"},
                        ],
                    }
                )
            ],
        )


def test_step09_merge_graph_delta_valid_single_root_tree_emits_expected_edges() -> None:
    payload = KnowledgeUpdatePayload(journal_reference="journal-1", requested_by_user_id="user-1", messages=[{"role": "user", "content": "hello", "created_at": "2026-03-02T12:00:00Z"}])
    merged = _build_step_nine_merge_graph_delta(
        payload=payload,
        step_zero_graph_delta={"entities": [], "blocks": [], "edges": [], "universes": []},
        step_two_extraction=EntityExtractionResult.model_validate({"extracted_entities": [], "extracted_universes": []}),
        step_seven_relationships=[],
        step_eight_final_entity_context_graphs=[
            FinalEntityContextGraph.model_validate(
                {
                    "entity": {"entity_id": "e1", "node_type": "node.person", "name": "Alice"},
                    "blocks": [
                        {"block_id": "root-1", "parent_block_id": "", "text": "root"},
                        {"block_id": "child-1", "parent_block_id": "root-1", "text": "child-1"},
                        {"block_id": "child-2", "parent_block_id": "root-1", "text": "child-2"},
                    ],
                }
            )
        ],
    )

    described_by_edges = [edge for edge in merged["edges"] if edge["edge_type"] == "DESCRIBED_BY"]
    assert len(described_by_edges) == 1
    assert described_by_edges[0]["from_id"] == "e1"

    summarizes_edges = [edge for edge in merged["edges"] if edge["edge_type"] == "SUMMARIZES"]
    assert len(summarizes_edges) == 2


class _FakeGrpcChannel:
    def __init__(self, context_by_type_id: dict[str, object]) -> None:
        self._context_by_type_id = context_by_type_id

    def unary_unary(self, _method: str, request_serializer, response_deserializer):
        async def _call(request):
            return self._context_by_type_id[request.type_id]

        return _call


@pytest.mark.asyncio
async def test_step10_preflight_rejects_missing_required_writable_property() -> None:
    from app.services.grpc import knowledge_pb2

    channel = _FakeGrpcChannel(
        {
            "node.person": knowledge_pb2.GetEntityTypePropertyContextReply(
                type_id="node.person",
                properties=[
                    knowledge_pb2.PropertyContext(prop_name="name", value_type="string", required=True, writable=True),
                ],
            )
        }
    )

    with pytest.raises(RuntimeError) as exc_info:
        await _preflight_validate_graph_delta_entities(
            channel=channel,
            graph_delta={
                "entities": [
                    {
                        "id": "entity-1",
                        "type_id": "node.person",
                        "properties": [{"key": "aliases", "json_value": '["A"]'}],
                    }
                ]
            },
            requesting_user_id="user-1",
        )

    message = str(exc_info.value)
    assert "step ten preflight" in message
    assert "entity_id=entity-1" in message
    assert "missing required writable properties: name" in message


@pytest.mark.asyncio
async def test_step10_preflight_rejects_wrong_property_value_type() -> None:
    from app.services.grpc import knowledge_pb2

    channel = _FakeGrpcChannel(
        {
            "node.person": knowledge_pb2.GetEntityTypePropertyContextReply(
                type_id="node.person",
                properties=[
                    knowledge_pb2.PropertyContext(prop_name="name", value_type="string", required=True, writable=True),
                ],
            )
        }
    )

    with pytest.raises(RuntimeError) as exc_info:
        await _preflight_validate_graph_delta_entities(
            channel=channel,
            graph_delta={
                "entities": [
                    {
                        "id": "entity-2",
                        "type_id": "node.person",
                        "properties": [{"key": "name", "int_value": 42}],
                    }
                ]
            },
            requesting_user_id="user-1",
        )

    message = str(exc_info.value)
    assert "step ten preflight" in message
    assert "entity_id=entity-2" in message
    assert "expects value_type 'string' but received 'int_value'" in message


def test_step10_preflight_edges_rejects_missing_provenance_hint() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        _preflight_validate_graph_delta_edges(
            {
                "edges": [
                    {
                        "from_id": "a",
                        "to_id": "b",
                        "edge_type": "REL",
                        "properties": [
                            {"key": "confidence", "float_value": 0.9},
                            {"key": "status", "string_value": "asserted"},
                        ],
                    }
                ]
            }
        )

    message = str(exc_info.value)
    assert "step ten preflight" in message
    assert "missing required edge property 'provenance_hint'" in message


def test_step10_preflight_edges_rejects_missing_status() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        _preflight_validate_graph_delta_edges(
            {
                "edges": [
                    {
                        "from_id": "a",
                        "to_id": "b",
                        "edge_type": "REL",
                        "properties": [
                            {"key": "confidence", "float_value": 0.9},
                            {"key": "provenance_hint", "string_value": "placeholder"},
                        ],
                    }
                ]
            }
        )

    message = str(exc_info.value)
    assert "step ten preflight" in message
    assert "missing required edge property 'status'" in message


def test_step10_preflight_edges_rejects_missing_confidence() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        _preflight_validate_graph_delta_edges(
            {
                "edges": [
                    {
                        "from_id": "a",
                        "to_id": "b",
                        "edge_type": "REL",
                        "properties": [
                            {"key": "status", "string_value": "asserted"},
                            {"key": "provenance_hint", "string_value": "placeholder"},
                        ],
                    }
                ]
            }
        )

    message = str(exc_info.value)
    assert "step ten preflight" in message
    assert "missing required edge property 'confidence'" in message


def test_step10_preflight_edges_accepts_valid_metadata() -> None:
    _preflight_validate_graph_delta_edges(
        {
            "edges": [
                {
                    "from_id": "a",
                    "to_id": "b",
                    "edge_type": "REL",
                    "properties": [
                        {"key": "confidence", "int_value": 1},
                        {"key": "status", "string_value": "asserted"},
                        {"key": "provenance_hint", "string_value": "placeholder"},
                    ],
                }
            ]
        }
    )
