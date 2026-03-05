from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from app.contracts import KnowledgeUpdatePayload
from app.services.grpc import knowledge_pb2
from app.worker.jobs.knowledge_update_types import (
    EntityExtractionResult,
    FinalEntityContextGraph,
    MatchedRelationship,
    RelationshipPair,
    ResolvedEntity,
)
from app.worker.jobs.knowledge_update import (
    _build_batch_document,
    _build_step_two_entity_extraction_json_schema,
    _build_step_two_entity_extraction_system_prompt,
    _build_upsert_graph_delta_step_one,
    _build_step_eight_final_entity_context_graph_schema,
    _build_step_nine_merge_graph_delta,
    _build_step_seven_relationship_match_schema,
    _build_step_six_relationship_extraction_schema,
    _build_step_ten_mentions_schema,
    _validate_upsert_graph_delta_payload,
    run,
    _classify_candidate_matches,
    _deduplicate_entity_pairs,
    _extract_matched_entity_id,
    _format_exception_for_stderr,
    _run_step_two_entity_extraction,
    _run_step_four_create_entity_contexts,
    _run_step_five_detailed_comparison,
    _run_step_six_relationship_extraction,
    _run_step_seven_match_relationship_type_and_score,
    _run_step_eight_build_final_entity_context_graphs,
    _run_step_ten_finalize_graph_delta,
    _step_two_store_batch_document,
)


class FakeInitGraphChannel:
    def __init__(self) -> None:
        self.calls = 0

    def unary_unary(self, method: str, request_serializer, response_deserializer):
        assert method == "/exobrain.knowledge.v1.KnowledgeInterface/GetUserInitGraph"
        assert request_serializer is not None
        assert response_deserializer is not None

        async def _call(request: knowledge_pb2.GetUserInitGraphRequest) -> knowledge_pb2.GetUserInitGraphReply:
            self.calls += 1
            assert request.user_id == "user-1"
            return knowledge_pb2.GetUserInitGraphReply(
                person_entity_id="person-entity-id",
                assistant_entity_id="assistant-entity-id",
            )

        return _call


class FakeEntityExtractionChannel:
    def unary_unary(self, method: str, request_serializer, response_deserializer):
        assert request_serializer is not None
        assert response_deserializer is not None

        async def _call(request):
            assert request.user_id == "user-1"
            if method.endswith("/GetEntityExtractionSchemaContext"):
                return knowledge_pb2.GetEntityExtractionSchemaContextReply()
            raise AssertionError(f"unexpected method: {method}")

        return _call


@pytest.mark.asyncio
async def test_step_zero_builds_upsert_graph_delta_request() -> None:
    payload = KnowledgeUpdatePayload(
        journal_reference="2026/03/02",
        requested_by_user_id="user-1",
        messages=[
            {
                "role": "user",
                "content": "hello",
                "sequence": 1,
                "created_at": "2026-03-02T12:00:00Z",
            }
        ],
    )

    channel = FakeInitGraphChannel()
    request_body = await _build_upsert_graph_delta_step_one(channel, payload)

    assert channel.calls == 1
    assert len(request_body["entities"]) == 1
    assert len(request_body["blocks"]) == 1
    assert len(request_body["edges"]) == 3


@pytest.mark.asyncio
async def test_step_zero_requires_created_at() -> None:
    payload = KnowledgeUpdatePayload(
        journal_reference="2026/03/02",
        requested_by_user_id="user-1",
        messages=[{"role": "user", "content": "hello"}],
    )

    with pytest.raises(ValueError) as exc_info:
        await _build_upsert_graph_delta_step_one(FakeInitGraphChannel(), payload)

    assert "missing created_at" in str(exc_info.value)


def test_format_exception_for_stderr_includes_traceback_and_message() -> None:
    try:
        raise ValueError("boom")
    except ValueError as exc:
        formatted = _format_exception_for_stderr(exc)

    assert "Traceback (most recent call last):" in formatted
    assert "ValueError: boom" in formatted


def test_build_batch_document_formats_header_and_turns() -> None:
    payload = KnowledgeUpdatePayload(
        journal_reference="journal-1",
        requested_by_user_id="user-1",
        messages=[
            {
                "role": "assistant",
                "content": "hi",
                "sequence": 7,
                "created_at": "2026-03-02T12:00:00Z",
            },
            {
                "role": " user role ",
                "content": None,
                "created_at": "2026-03-02T12:05:00Z",
            },
        ],
    )

    assert _build_batch_document(payload).startswith("=== BATCH DOCUMENT ===")
    assert "--- TURN 7 ---" in _build_batch_document(payload)


def test_step_two_logs_batch_document(caplog: pytest.LogCaptureFixture) -> None:
    payload = KnowledgeUpdatePayload(
        journal_reference="journal-1",
        requested_by_user_id="user-1",
        messages=[{"role": "user", "content": "hello"}],
    )

    with caplog.at_level(logging.INFO):
        document = _step_two_store_batch_document(payload)

    assert "knowledge.update step one batch document" in caplog.text
    assert "conversation_id: journal-1" in document


def test_step_two_schema_requires_expected_fields() -> None:
    schema = _build_step_two_entity_extraction_json_schema()

    assert schema["required"] == ["extracted_entities", "extracted_universes"]
    assert schema["properties"]["extracted_entities"]["items"]["required"] == [
        "name",
        "node_type",
        "aliases",
        "short_description",
    ]


def test_step_two_prompt_includes_schema_context() -> None:
    prompt = _build_step_two_entity_extraction_system_prompt({"entity_types": [{"type_id": "node.person"}]})

    assert "knowledge.update entity extraction worker" in prompt
    assert "Entity extraction schema context (JSON)" in prompt
    assert "node.person" in prompt


@pytest.mark.asyncio
async def test_run_step_two_entity_extraction_uses_worker_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings import Settings
    import langchain.agents

    captured: dict[str, object] = {}

    class FakeCompiledAgent:
        async def ainvoke(self, payload: dict[str, object]) -> dict[str, object]:
            captured["ainvoke_payload"] = payload
            return {
                "structured_response": {
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
            }

    def fake_create_agent(*, model, tools, system_prompt, response_format):
        captured["model_name"] = model.model
        captured["tools"] = tools
        captured["system_prompt"] = system_prompt
        captured["response_format"] = response_format
        return FakeCompiledAgent()

    monkeypatch.setattr(langchain.agents, "create_agent", fake_create_agent)

    payload = KnowledgeUpdatePayload(
        journal_reference="journal-1",
        requested_by_user_id="user-1",
        messages=[{"role": "user", "content": "hello", "created_at": "2026-03-02T12:00:00Z"}],
    )

    result = await _run_step_two_entity_extraction(
        FakeEntityExtractionChannel(),
        payload,
        "--- TURN 1 ---",
        Settings(model_provider_base_url="http://provider", knowledge_update_extraction_model="worker"),
    )

    assert result.extracted_entities[0].name == "Alice"
    assert result.extracted_universes == []
    assert captured["model_name"] == "worker"
    assert captured["tools"] == []
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert captured["response_format"]["json_schema"]["schema"]["required"] == ["extracted_entities", "extracted_universes"]


def test_classify_candidate_matches_uses_requested_thresholds() -> None:
    assert _classify_candidate_matches([])["status"] == "new_entity"

    strong_match = _classify_candidate_matches([
        {"entity_id": "entity-1", "score": 0.61},
        {"entity_id": "entity-2", "score": 0.2},
    ])
    assert strong_match["status"] == "matched"
    assert strong_match["matched_entity_id"] == "entity-1"

    detail_match = _classify_candidate_matches([
        {"entity_id": "entity-1", "score": 0.4},
        {"entity_id": "entity-2", "score": 0.2},
        {"entity_id": "entity-3", "score": 0.1},
    ])
    assert detail_match == {
        "status": "needs_detailed_comparison",
        "candidate_entity_ids": ["entity-1", "entity-2"],
    }






def test_step_eight_final_entity_context_graph_schema_requires_entity_and_blocks() -> None:
    schema = _build_step_eight_final_entity_context_graph_schema()

    assert schema["required"] == ["entity", "blocks"]
    assert schema["properties"]["blocks"]["items"]["required"] == ["block_id", "text"]
def test_step_six_relationship_extraction_schema_requires_entity_pairs() -> None:
    schema = _build_step_six_relationship_extraction_schema()

    assert schema["required"] == ["entity_pairs"]
    assert schema["properties"]["entity_pairs"]["items"]["required"] == ["entity_id_1", "entity_id_2"]


def test_step_seven_relationship_match_schema_requires_confidence() -> None:
    schema = _build_step_seven_relationship_match_schema()

    assert schema["required"] == ["from_entity_id", "to_entity_id", "edge_type", "confidence"]


def test_deduplicate_entity_pairs_filters_invalid_and_duplicates() -> None:
    pairs = _deduplicate_entity_pairs(
        [
            RelationshipPair(entity_id_1="a", entity_id_2="b"),
            RelationshipPair(entity_id_1="b", entity_id_2="a"),
            RelationshipPair(entity_id_1="a", entity_id_2="a"),
            RelationshipPair(entity_id_1="a", entity_id_2="missing"),
        ],
        valid_entity_ids={"a", "b"},
    )

    assert pairs == [RelationshipPair(entity_id_1="a", entity_id_2="b")]
def test_extract_matched_entity_id_parses_expected_decisions() -> None:
    assert _extract_matched_entity_id("MATCH(entity-1)") == "entity-1"
    assert _extract_matched_entity_id("NEW_ENTITY") is None
    assert _extract_matched_entity_id("unknown") is None

def test_step_ten_mentions_schema_requires_mentions() -> None:
    schema = _build_step_ten_mentions_schema()

    assert schema["required"] == ["mentions"]
    assert schema["properties"]["mentions"]["items"]["required"] == ["block_id", "entity_id", "confidence"]


def test_step_nine_merge_graph_delta_maps_blocks_edges_and_universes() -> None:
    payload = KnowledgeUpdatePayload(
        journal_reference="journal-1",
        requested_by_user_id="user-1",
        messages=[{"role": "user", "content": "hello", "created_at": "2026-03-02T12:00:00Z"}],
    )

    merged = _build_step_nine_merge_graph_delta(
        payload=payload,
        step_zero_graph_delta={"entities": [], "blocks": [], "edges": [], "universes": []},
        step_two_extraction=EntityExtractionResult.model_validate(
            {
                "extracted_entities": [],
                "extracted_universes": [{"name": "Wonderland", "description": "fictional"}],
            }
        ),
        step_seven_relationships=[
            MatchedRelationship(
                from_entity_id="e1",
                to_entity_id="e2",
                edge_type="edge.related_to",
                confidence=0.8,
            )
        ],
        step_eight_final_entity_context_graphs=[
            FinalEntityContextGraph.model_validate(
                {
                    "entity": {
                        "entity_id": "e1",
                        "node_type": "node.person",
                        "name": "Alice",
                        "aliases": ["A"],
                        "universe_name": "Wonderland",
                    },
                    "blocks": [
                        {"block_id": "NEW_BLOCK_1", "parent_block_id": "", "text": "root"},
                        {"block_id": "NEW_BLOCK_2", "parent_block_id": "NEW_BLOCK_1", "text": "child"},
                    ],
                }
            )
        ],
    )

    assert len(merged["universes"]) == 1
    assert len(merged["entities"]) == 1
    assert len(merged["blocks"]) == 2
    edge_types = {edge["edge_type"] for edge in merged["edges"]}
    assert "DESCRIBED_BY" in edge_types
    assert "SUMMARIZES" in edge_types
    assert "edge.related_to" in edge_types


class _NoopChannel:
    def unary_unary(self, method: str, request_serializer, response_deserializer):
        assert request_serializer is not None
        assert response_deserializer is not None

        async def _call(request):
            if method.endswith("/GetEntityContext"):
                return knowledge_pb2.GetEntityContextReply()
            if method.endswith("/GetEdgeExtractionSchemaContext"):
                return knowledge_pb2.GetEdgeExtractionSchemaContextReply()
            if method.endswith("/GetEntityTypePropertyContext"):
                return knowledge_pb2.GetEntityTypePropertyContextReply()
            raise AssertionError(f"unexpected method: {method}")

        return _call


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("runner_name", "runner_args"),
    [
        (
            "_run_step_two_entity_extraction",
            lambda settings: (FakeEntityExtractionChannel(), KnowledgeUpdatePayload(
                journal_reference="journal-1",
                requested_by_user_id="user-1",
                messages=[{"role": "user", "content": "hello", "created_at": "2026-03-02T12:00:00Z"}],
            ), "--- TURN 1 ---", settings),
        ),
        (
            "_run_step_four_create_entity_contexts",
            lambda settings: (
                EntityExtractionResult.model_validate({
                    "extracted_entities": [{"name": "Alice", "node_type": "node.person", "aliases": [], "short_description": "A person"}],
                    "extracted_universes": [],
                }),
                "--- TURN 1 ---",
                settings,
            ),
        ),
        (
            "_run_step_five_detailed_comparison",
            lambda settings: (
                _NoopChannel(),
                KnowledgeUpdatePayload(journal_reference="journal-1", requested_by_user_id="user-1", messages=[]),
                [],
                [],
                settings,
            ),
        ),
        (
            "_run_step_six_relationship_extraction",
            lambda settings: (
                [],
                "--- TURN 1 ---",
                settings,
            ),
        ),
        (
            "_run_step_seven_match_relationship_type_and_score",
            lambda settings: (
                _NoopChannel(),
                KnowledgeUpdatePayload(journal_reference="journal-1", requested_by_user_id="user-1", messages=[]),
                [],
                ["# Alice"],
                [],
                settings,
            ),
        ),
        (
            "_run_step_eight_build_final_entity_context_graphs",
            lambda settings: (
                _NoopChannel(),
                KnowledgeUpdatePayload(journal_reference="journal-1", requested_by_user_id="user-1", messages=[]),
                [
                    ResolvedEntity.model_validate(
                        {
                            "entity_index": 0,
                            "resolution_status": "new_entity",
                            "resolved_entity_id": "entity-1",
                            "extracted_entity": {"name": "Alice", "node_type": "node.person", "aliases": [], "short_description": "A person"},
                        }
                    )
                ],
                ["# Alice"],
                settings,
            ),
        ),
        (
            "_run_step_ten_finalize_graph_delta",
            lambda settings: (
                {"entities": [], "blocks": [], "edges": []},
                settings,
                "user-1",
            ),
        ),
    ],
)
async def test_worker_agents_use_strict_response_format(monkeypatch: pytest.MonkeyPatch, runner_name: str, runner_args) -> None:
    import app.worker.jobs.knowledge_update as knowledge_update
    import langchain.agents
    from app.settings import Settings

    captured: dict[str, object] = {}

    class FakeCompiledAgent:
        async def ainvoke(self, payload: dict[str, object]) -> dict[str, object]:
            if runner_name == "_run_step_two_entity_extraction":
                return {"structured_response": {"extracted_entities": [], "extracted_universes": []}}
            if runner_name == "_run_step_four_create_entity_contexts":
                return {"structured_response": {"focused_markdown": "# entity"}}
            if runner_name == "_run_step_five_detailed_comparison":
                return {"structured_response": {"decision": "NEW_ENTITY"}}
            if runner_name == "_run_step_six_relationship_extraction":
                return {"structured_response": {"entity_pairs": []}}
            if runner_name == "_run_step_seven_match_relationship_type_and_score":
                return {"structured_response": {"from_entity_id": "entity-1", "to_entity_id": "entity-1", "edge_type": "edge.related", "confidence": 0.9}}
            if runner_name == "_run_step_eight_build_final_entity_context_graphs":
                return {"structured_response": {"entity": {"entity_id": "entity-1", "node_type": "node.person"}, "blocks": []}}
            return {"structured_response": {"mentions": []}}

    def fake_create_agent(*, model, tools, system_prompt, response_format):
        captured["response_format"] = response_format
        return FakeCompiledAgent()

    monkeypatch.setattr(langchain.agents, "create_agent", fake_create_agent)

    settings = Settings(model_provider_base_url="http://provider", knowledge_update_extraction_model="worker")
    runner = getattr(knowledge_update, runner_name)
    args = runner_args(settings)
    await runner(*args)

    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["strict"] is True


def test_validate_upsert_graph_delta_payload_reports_invalid_field_path() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        _validate_upsert_graph_delta_payload(
            "step nine",
            {
                "entities": [
                    {
                        "id": "entity-1",
                        "type_id": "node.person",
                        "user_id": "user-1",
                        "visibility": "PRIVATE",
                        "properties": [{"key": "name", "string_value": "Alice", "invalid_field": "nope"}],
                    }
                ]
            },
        )

    assert "step nine" in str(exc_info.value)
    assert "entities.properties" in str(exc_info.value)


class _FakeGrpcChannelContext:
    def __init__(self) -> None:
        self._upsert_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def channel_ready(self) -> None:
        return None

    def unary_unary(self, method: str, request_serializer, response_deserializer):
        assert request_serializer is not None
        assert response_deserializer is not None

        async def _call(request):
            self._upsert_calls += 1
            return knowledge_pb2.UpsertGraphDeltaReply(entities_upserted=1, blocks_upserted=1, edges_upserted=1)

        return _call


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("invalid_step", "expected_step", "expected_path"),
    [
        ("step_zero", "step zero", "entities.properties"),
        ("step_nine", "step nine", "entities.properties"),
        ("step_ten", "step ten", "entities.properties"),
    ],
)
async def test_run_fails_fast_with_step_specific_parse_dict_validation(
    monkeypatch: pytest.MonkeyPatch,
    invalid_step: str,
    expected_step: str,
    expected_path: str,
) -> None:
    import app.worker.jobs.knowledge_update as knowledge_update

    payload = {
        "journal_reference": "journal-1",
        "requested_by_user_id": "user-1",
        "messages": [{"role": "user", "content": "hello", "created_at": "2026-03-02T12:00:00Z"}],
    }
    job = SimpleNamespace(payload=payload)

    valid_graph = {"entities": [], "blocks": [], "edges": [], "universes": []}
    invalid_graph = {
        "entities": [
            {
                "id": "entity-1",
                "type_id": "node.person",
                "user_id": "user-1",
                "visibility": "PRIVATE",
                "properties": [{"key": "name", "string_value": "Alice", "invalid_field": "bad"}],
            }
        ],
        "blocks": [],
        "edges": [],
        "universes": [],
    }

    async def fake_step_zero(channel, parsed_payload):
        assert parsed_payload.requested_by_user_id == "user-1"
        return invalid_graph if invalid_step == "step_zero" else valid_graph

    monkeypatch.setattr(knowledge_update, "_build_upsert_graph_delta_step_one", fake_step_zero)
    monkeypatch.setattr(knowledge_update, "_step_two_store_batch_document", lambda _payload: "doc")

    async def fake_step_two(*_args, **_kwargs):
        return EntityExtractionResult.model_validate({"extracted_entities": [], "extracted_universes": []})

    async def fake_step_three(*_args, **_kwargs):
        return []

    async def fake_step_four(*_args, **_kwargs):
        return []

    async def fake_step_five(*_args, **_kwargs):
        return []

    async def fake_step_six(*_args, **_kwargs):
        return []

    async def fake_step_seven(*_args, **_kwargs):
        return []

    async def fake_step_eight(*_args, **_kwargs):
        return []

    def fake_step_nine(*_args, **_kwargs):
        return invalid_graph if invalid_step == "step_nine" else valid_graph

    async def fake_step_ten(*_args, **_kwargs):
        return invalid_graph if invalid_step == "step_ten" else valid_graph

    monkeypatch.setattr(knowledge_update, "_run_step_two_entity_extraction", fake_step_two)
    monkeypatch.setattr(knowledge_update, "_run_step_three_entity_candidate_matching", fake_step_three)
    monkeypatch.setattr(knowledge_update, "_run_step_four_create_entity_contexts", fake_step_four)
    monkeypatch.setattr(knowledge_update, "_run_step_five_detailed_comparison", fake_step_five)
    monkeypatch.setattr(knowledge_update, "_run_step_six_relationship_extraction", fake_step_six)
    monkeypatch.setattr(knowledge_update, "_run_step_seven_match_relationship_type_and_score", fake_step_seven)
    monkeypatch.setattr(knowledge_update, "_run_step_eight_build_final_entity_context_graphs", fake_step_eight)
    monkeypatch.setattr(knowledge_update, "_build_step_nine_merge_graph_delta", fake_step_nine)
    monkeypatch.setattr(knowledge_update, "_run_step_ten_finalize_graph_delta", fake_step_ten)

    monkeypatch.setattr(knowledge_update, "get_settings", lambda: SimpleNamespace(
        knowledge_interface_grpc_target="localhost:50051",
        knowledge_interface_connect_timeout_seconds=0.1,
    ))
    monkeypatch.setattr(knowledge_update.grpc.aio, "insecure_channel", lambda _target: _FakeGrpcChannelContext())

    with pytest.raises(RuntimeError) as exc_info:
        await run(job)

    error_message = str(exc_info.value)
    assert expected_step in error_message
    assert expected_path in error_message
