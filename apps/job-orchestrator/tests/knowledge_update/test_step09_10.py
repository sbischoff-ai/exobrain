from __future__ import annotations

import pytest

from app.contracts import KnowledgeUpdatePayload
from app.worker.jobs.knowledge_update import (
    _build_step_nine_merge_graph_delta,
    _build_step_ten_mentions_schema,
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
        step_eight_final_entity_context_graphs=[FinalEntityContextGraph.model_validate({"entity": {"entity_id": "e1", "node_type": "node.person", "name": "Alice", "aliases": ["A"], "universe_name": "Wonderland"}, "blocks": [{"block_id": "NEW_BLOCK_1", "parent_block_id": "", "text": "root"}]})],
    )
    assert len(merged["universes"]) == 1
    assert len(merged["entities"]) == 1


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
