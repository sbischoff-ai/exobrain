from __future__ import annotations

import pytest

from app.contracts import KnowledgeUpdatePayload
from app.settings import Settings
from app.services.grpc import knowledge_pb2
from app.worker.jobs.knowledge_update import (
    _run_step_eight_build_final_entity_context_graphs,
    _run_step_five_detailed_comparison,
    _run_step_four_create_entity_contexts,
    _run_step_seven_match_relationship_type_and_score,
    _run_step_six_relationship_extraction,
    _run_step_ten_finalize_graph_delta,
)
from app.worker.jobs.knowledge_update_types import (
    CandidateMatchResult,
    EntityExtractionResult,
    ExtractedEntity,
    RelationshipPair,
    ResolvedEntity,
)


def _assert_strict_response_format(payload: object) -> None:
    assert isinstance(payload, dict)
    assert payload.get("type") == "json_schema"
    json_schema = payload.get("json_schema")
    assert isinstance(json_schema, dict)
    assert json_schema.get("strict") is True


@pytest.mark.asyncio
async def test_steps_04_05_06_use_strict_response_formats(monkeypatch: pytest.MonkeyPatch) -> None:
    import langchain.agents

    captured: list[dict[str, object]] = []

    class FakeCompiledAgent:
        def __init__(self, response: dict[str, object]) -> None:
            self._response = response

        async def ainvoke(self, _payload: dict[str, object]) -> dict[str, object]:
            return {"structured_response": self._response}

    def _create_agent(**kwargs):
        captured.append(kwargs)
        response_format = kwargs["response_format"]
        json_schema = response_format["json_schema"]["schema"]
        if "focused_markdown" in json_schema.get("properties", {}):
            return FakeCompiledAgent({"focused_markdown": "# Focused\nDetails"})
        if "decision" in json_schema.get("properties", {}):
            return FakeCompiledAgent({"decision": "NEW_ENTITY"})
        return FakeCompiledAgent({"entity_pairs": [{"entity_id_1": "entity-1", "entity_id_2": "entity-2"}]})

    monkeypatch.setattr(langchain.agents, "create_agent", _create_agent)

    settings = Settings(model_provider_base_url="http://provider")
    extraction = EntityExtractionResult.model_validate(
        {
            "extracted_entities": [
                {
                    "name": "Alice",
                    "node_type": "node.person",
                    "aliases": [],
                    "short_description": "A person",
                }
            ],
            "extracted_universes": [],
        }
    )

    docs = await _run_step_four_create_entity_contexts(extraction, "batch", settings)
    assert docs[0].startswith("# Focused")

    matched_candidate = CandidateMatchResult.model_validate(
        {
            "entity_index": 0,
            "extracted_entity": extraction.extracted_entities[0].model_dump(),
            "candidate_matches": [],
            "status": "matched",
            "candidate_entity_ids": [],
            "matched_entity_id": "entity-1",
        }
    )
    resolved = await _run_step_five_detailed_comparison(
        channel=_FakeStepFiveChannel(),
        payload=KnowledgeUpdatePayload(
            journal_reference="journal-1",
            requested_by_user_id="user-1",
            messages=[{"role": "user", "content": "hello", "created_at": "2026-03-02T12:00:00Z"}],
        ),
        candidate_matching=[matched_candidate],
        entity_context_documents=docs,
        settings=settings,
    )
    assert resolved[0].resolved_entity_id == "entity-1"

    pairs = await _run_step_six_relationship_extraction(resolved, "batch", settings)
    assert isinstance(pairs, list)

    assert len(captured) == 3
    for item in captured:
        _assert_strict_response_format(item["response_format"])


class _FakeStepFiveChannel:
    def unary_unary(self, method: str, request_serializer, response_deserializer):
        async def _call(_request):
            if method.endswith("/GetEntityContext"):
                return knowledge_pb2.GetEntityContextReply()
            raise AssertionError(method)

        return _call


class _FakeStepSevenChannel:
    def unary_unary(self, method: str, request_serializer, response_deserializer):
        async def _call(_request):
            if method.endswith("/GetEdgeExtractionSchemaContext"):
                return knowledge_pb2.GetEdgeExtractionSchemaContextReply()
            if method.endswith("/GetEntityTypePropertyContext"):
                return knowledge_pb2.GetEntityTypePropertyContextReply()
            raise AssertionError(method)

        return _call


@pytest.mark.asyncio
async def test_steps_07_08_10_use_strict_response_formats(monkeypatch: pytest.MonkeyPatch) -> None:
    import langchain.agents

    captured: list[dict[str, object]] = []

    class FakeCompiledAgent:
        def __init__(self, response: dict[str, object]) -> None:
            self._response = response

        async def ainvoke(self, _payload: dict[str, object]) -> dict[str, object]:
            return {"structured_response": self._response}

    def _create_agent(**kwargs):
        captured.append(kwargs)
        response_format = kwargs["response_format"]
        json_schema = response_format["json_schema"]["schema"]
        properties = json_schema.get("properties", {})
        if "edge_type" in properties:
            return FakeCompiledAgent(
                {
                    "from_entity_id": "entity-1",
                    "to_entity_id": "entity-2",
                    "edge_type": "edge.related_to",
                    "confidence": 0.9,
                }
            )
        if "mentions" in properties:
            return FakeCompiledAgent(
                {
                    "mentions": [
                        {"block_id": "block-1", "entity_id": "entity-1", "confidence": 0.8},
                    ]
                }
            )
        return FakeCompiledAgent(
            {
                "entity_id": "entity-1",
                "node_type": "node.person",
                "name": "Alice",
                "aliases": ["A"],
                "entity": {
                    "entity_id": "entity-1",
                    "node_type": "node.person",
                    "name": "Alice",
                    "aliases": ["A"],
                    "short_description": "A person",
                },
                "blocks": [{"block_id": "NEW_BLOCK_1", "text": "root"}],
            }
        )

    monkeypatch.setattr(langchain.agents, "create_agent", _create_agent)

    settings = Settings(model_provider_base_url="http://provider")
    payload = KnowledgeUpdatePayload(
        journal_reference="journal-1",
        requested_by_user_id="user-1",
        messages=[{"role": "user", "content": "hello", "created_at": "2026-03-02T12:00:00Z"}],
    )
    resolved = [
        ResolvedEntity(
            entity_index=0,
            extracted_entity=ExtractedEntity(
                name="Alice",
                node_type="node.person",
                aliases=["A"],
                short_description="A person",
                universe_id=None,
            ),
            resolved_entity_id="entity-1",
            resolution_status="new_entity",
        ),
        ResolvedEntity(
            entity_index=1,
            extracted_entity=ExtractedEntity(
                name="Bob",
                node_type="node.person",
                aliases=[],
                short_description="A person",
                universe_id=None,
            ),
            resolved_entity_id="entity-2",
            resolution_status="new_entity",
        ),
    ]
    contexts = ["# Alice", "# Bob"]

    matched = await _run_step_seven_match_relationship_type_and_score(
        _FakeStepSevenChannel(),
        payload,
        resolved,
        contexts,
        [RelationshipPair(entity_id_1="entity-1", entity_id_2="entity-2")],
        settings,
    )
    assert matched[0].edge_type == "edge.related_to"

    with pytest.raises(RuntimeError, match="step eight validation failed"):
        await _run_step_eight_build_final_entity_context_graphs(
            _FakeStepSevenChannel(),
            payload,
            [resolved[0]],
            [contexts[0]],
            settings,
        )

    merged = {
        "entities": [{"id": "entity-1", "properties": [{"key": "name", "string_value": "Alice"}]}],
        "blocks": [{"id": "block-1", "properties": [{"key": "text", "string_value": "alice text"}]}],
        "edges": [],
        "universes": [],
    }
    finalized = await _run_step_ten_finalize_graph_delta(merged, settings, "user-1")
    assert len(finalized["edges"]) == 1

    assert len(captured) == 3
    for item in captured:
        _assert_strict_response_format(item["response_format"])
