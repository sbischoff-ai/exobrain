from __future__ import annotations

import logging

import pytest

from app.contracts import KnowledgeUpdatePayload
from app.services.grpc import knowledge_pb2
from app.worker.jobs.knowledge_update import (
    _append_mentions_edges,
    _build_batch_document,
    _format_exception_for_stderr,
    _build_step_four_router_json_schema,
    _build_step_four_router_prompt,
    _build_step_three_system_prompt,
    _build_upsert_graph_delta_step_one,
    _merge_upsert_graph_delta_requests,
    _step_two_store_batch_document,
)


class FakeChannel:
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


@pytest.mark.asyncio
async def test_step_one_builds_upsert_graph_delta_request() -> None:
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

    channel = FakeChannel()
    request_body = await _build_upsert_graph_delta_step_one(channel, payload)

    assert channel.calls == 1
    assert len(request_body["entities"]) == 1
    assert len(request_body["blocks"]) == 1
    assert len(request_body["edges"]) == 3

    entity_properties = {item["key"]: item for item in request_body["entities"][0]["properties"]}
    assert entity_properties["name"]["string_value"] == "2026/03/02 message 1"
    assert entity_properties["start"]["datetime_value"] == "2026-03-02T12:00:00Z"
    assert entity_properties["end"]["datetime_value"] == "2026-03-02T12:00:00Z"

    edge_types = {edge["edge_type"] for edge in request_body["edges"]}
    assert edge_types == {"SENT_TO", "SENT_BY", "DESCRIBED_BY"}


@pytest.mark.asyncio
async def test_step_one_requires_created_at() -> None:
    payload = KnowledgeUpdatePayload(
        journal_reference="2026/03/02",
        requested_by_user_id="user-1",
        messages=[{"role": "user", "content": "hello"}],
    )

    with pytest.raises(ValueError) as exc_info:
        await _build_upsert_graph_delta_step_one(FakeChannel(), payload)

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

    assert _build_batch_document(payload) == """=== BATCH DOCUMENT ===
conversation_id: journal-1
user_id: user-1
time_range_start: 2026-03-02T12:00:00Z
time_range_end: 2026-03-02T12:05:00Z

--- TURN 7 ---
speaker: ASSISTANT
timestamp: 2026-03-02T12:00:00Z
content:
hi

--- TURN 2 ---
speaker: USER_ROLE
timestamp: 2026-03-02T12:05:00Z
content:"""


def test_build_batch_document_without_header_and_missing_timestamps() -> None:
    payload = KnowledgeUpdatePayload(
        journal_reference="journal-1",
        requested_by_user_id="user-1",
        messages=[
            {
                "role": "",
                "content": "first",
            },
            {
                "role": "assistant-reply",
                "content": "second",
                "sequence": 4,
            },
        ],
    )

    assert _build_batch_document(payload, include_header=False) == """--- TURN 1 ---
speaker: UNKNOWN
timestamp: unknown
content:
first

--- TURN 4 ---
speaker: ASSISTANT_REPLY
timestamp: unknown
content:
second"""


def test_step_two_logs_batch_document(caplog: pytest.LogCaptureFixture) -> None:
    payload = KnowledgeUpdatePayload(
        journal_reference="journal-1",
        requested_by_user_id="user-1",
        messages=[{"role": "user", "content": "hello"}],
    )

    with caplog.at_level(logging.INFO):
        document = _step_two_store_batch_document(payload)

    assert "knowledge.update step two batch document" in caplog.text
    assert "conversation_id: journal-1" in document


def test_merge_upsert_graph_delta_requests_combines_all_sections() -> None:
    left = {"entities": [{"id": "e1"}], "blocks": [], "edges": [{"id": "edge-1"}]}
    right = {"universes": [{"id": "u1"}], "entities": [{"id": "e2"}], "blocks": [{"id": "b1"}]}

    merged = _merge_upsert_graph_delta_requests(left, right)

    assert merged == {
        "universes": [{"id": "u1"}],
        "entities": [{"id": "e1"}, {"id": "e2"}],
        "blocks": [{"id": "b1"}],
        "edges": [{"id": "edge-1"}],
    }


def test_build_step_three_system_prompt_includes_required_guidance() -> None:
    prompt = _build_step_three_system_prompt({'entity_types': []}, '{"type":"object"}')

    assert "knowledge.update extraction architect" in prompt
    assert "block_level <= 2" in prompt
    assert "fictional context" in prompt
    assert "assistant suggestions must be ignored unless the user approved" in prompt.lower()
    assert "Entity extraction schema context (JSON)" in prompt
    assert "get_edge_extraction_schema_context" in prompt
    assert '{"type":"object"}' in prompt


def test_build_step_four_router_json_schema_requires_mapping_fields() -> None:
    schema = _build_step_four_router_json_schema()

    mapping_required = schema["properties"]["mappings"]["items"]["required"]
    assert mapping_required == ["block_id", "entity_id", "confidence"]


def test_build_step_four_router_prompt_includes_block_and_entity_summaries() -> None:
    step_one = {
        "blocks": [
            {
                "id": "block-1",
                "properties": [{"key": "text", "string_value": "Alice met Bob"}],
            }
        ]
    }
    step_three = {
        "entities": [
            {
                "id": "entity-1",
                "type_id": "node.person",
                "properties": [
                    {"key": "name", "string_value": "Alice"},
                    {"key": "described_by_text", "string_value": "A colleague"},
                ],
            }
        ]
    }

    prompt = _build_step_four_router_prompt(step_one, step_three)

    assert '"block_id": "block-1"' in prompt
    assert '"entity_id": "entity-1"' in prompt
    assert '"Alice met Bob"' in prompt


def test_append_mentions_edges_adds_valid_mappings_only() -> None:
    merged = {"edges": [{"from_id": "x", "to_id": "y", "edge_type": "EXISTING"}]}
    step_one = {"blocks": [{"id": "block-1"}]}
    step_three = {"entities": [{"id": "entity-1"}]}

    _append_mentions_edges(
        merged,
        step_one,
        step_three,
        mappings=[
            {"block_id": "block-1", "entity_id": "entity-1", "confidence": 0.9},
            {"block_id": "missing", "entity_id": "entity-1", "confidence": 0.8},
            {"block_id": "block-1", "entity_id": "missing", "confidence": 0.8},
            {"block_id": "block-1", "entity_id": "entity-1", "confidence": "high"},
        ],
        user_id="user-1",
    )

    assert len(merged["edges"]) == 2
    mentions_edge = merged["edges"][1]
    assert mentions_edge["edge_type"] == "MENTIONS"
    assert mentions_edge["from_id"] == "block-1"
    assert mentions_edge["to_id"] == "entity-1"
    assert mentions_edge["visibility"] == "PRIVATE"
    assert mentions_edge["properties"] == [{"key": "confidence", "float_value": 0.9}]

class _FakeExtractionChannel:
    def unary_unary(self, method: str, request_serializer, response_deserializer):
        assert request_serializer is not None
        assert response_deserializer is not None

        async def _call(request):
            if method.endswith("/GetEntityExtractionSchemaContext"):
                return knowledge_pb2.GetEntityExtractionSchemaContextReply()
            if method.endswith("/GetEdgeExtractionSchemaContext"):
                return knowledge_pb2.GetEdgeExtractionSchemaContextReply()
            if method.endswith("/GetUpsertGraphDeltaJsonSchema"):
                return knowledge_pb2.GetUpsertGraphDeltaJsonSchemaReply(
                    json_schema='{"type":"object","properties":{"entities":{"type":"array"}}}'
                )
            if method.endswith("/FindEntityCandidates"):
                return knowledge_pb2.FindEntityCandidatesReply()
            if method.endswith("/GetEntityContext"):
                return knowledge_pb2.GetEntityContextReply()
            if method.endswith("/GetEntityTypePropertyContext"):
                return knowledge_pb2.GetEntityTypePropertyContextReply()
            raise AssertionError(f"unexpected method: {method}")

        return _call


@pytest.mark.asyncio
async def test_run_step_three_extraction_agent_uses_model_provider_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings import Settings
    from app.worker.jobs import knowledge_update

    captured: dict[str, object] = {}

    class FakeCompiledAgent:
        async def ainvoke(self, payload: dict[str, object]) -> dict[str, object]:
            captured["ainvoke_payload"] = payload
            return {"structured_response": {"entities": [{"id": "entity-1"}]}}

    def fake_create_agent(*, model, tools, system_prompt, response_format):
        captured["model_class"] = model.__class__.__name__
        captured["tools"] = [tool.name for tool in tools]
        captured["serialized_tools"] = [model._serialize_tool(tool) for tool in tools]
        captured["response_format"] = response_format
        captured["system_prompt"] = system_prompt
        return FakeCompiledAgent()

    # Patch the imported symbol inside function scope via langchain.agents module.
    import langchain.agents

    monkeypatch.setattr(langchain.agents, "create_agent", fake_create_agent)

    payload = KnowledgeUpdatePayload(
        journal_reference="journal-1",
        requested_by_user_id="user-1",
        messages=[{"role": "user", "content": "hello", "created_at": "2026-03-02T12:00:00Z"}],
    )

    settings = Settings(model_provider_base_url="http://provider")
    result = await knowledge_update._run_step_three_extraction_agent(
        _FakeExtractionChannel(), payload, "--- TURN 1 ---", settings
    )

    assert result == {"entities": [{"id": "entity-1"}]}
    assert captured["model_class"] == "ModelProviderChatModel"
    assert captured["tools"] == [
        "get_edge_extraction_schema_context",
        "find_entity_candidates",
        "get_entity_context",
        "get_entity_type_property_context",
    ]
    assert all(item["type"] == "function" for item in captured["serialized_tools"])
    assert all("parameters" in item for item in captured["serialized_tools"])
    assert captured["response_format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_run_step_three_edge_context_tool_handles_empty_rpc_reply(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.settings import Settings
    from app.worker.jobs import knowledge_update

    class EmptyEdgeContextChannel(_FakeExtractionChannel):
        def unary_unary(self, method: str, request_serializer, response_deserializer):
            wrapped = super().unary_unary(method, request_serializer, response_deserializer)

            async def _call(request):
                if method.endswith("/GetEdgeExtractionSchemaContext"):
                    return None
                return await wrapped(request)

            return _call

    class FakeCompiledAgent:
        async def ainvoke(self, payload: dict[str, object]) -> dict[str, object]:
            edge_tool = captured_tools["get_edge_extraction_schema_context"]
            tool_result = await edge_tool.ainvoke(
                {
                    "source_entity_type_id": "node.person",
                    "target_entity_type_id": "node.organization",
                }
            )
            assert tool_result == {
                "source_entity_type_id": "node.person",
                "target_entity_type_id": "node.organization",
                "entity_types": [],
            }
            return {"structured_response": {"entities": []}}

    captured_tools: dict[str, object] = {}

    def fake_create_agent(*, model, tools, system_prompt, response_format):
        del model, system_prompt, response_format
        for tool in tools:
            captured_tools[tool.name] = tool
        return FakeCompiledAgent()

    import langchain.agents

    monkeypatch.setattr(langchain.agents, "create_agent", fake_create_agent)

    payload = KnowledgeUpdatePayload(
        journal_reference="journal-1",
        requested_by_user_id="user-1",
        messages=[{"role": "user", "content": "hello", "created_at": "2026-03-02T12:00:00Z"}],
    )

    with caplog.at_level(logging.WARNING):
        result = await knowledge_update._run_step_three_extraction_agent(
            EmptyEdgeContextChannel(), payload, "--- TURN 1 ---", Settings(model_provider_base_url="http://provider")
        )

    assert result == {"entities": []}
    assert "received empty edge extraction schema context" in caplog.text


@pytest.mark.asyncio
async def test_run_step_four_router_agent_returns_structured_response(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings import Settings
    from app.worker.jobs import knowledge_update

    class FakeCompiledAgent:
        async def ainvoke(self, payload: dict[str, object]) -> dict[str, object]:
            return {
                "structured_response": {
                    "mappings": [
                        {
                            "block_id": "block-1",
                            "entity_id": "entity-1",
                            "confidence": 0.95,
                            "reason": "explicit mention",
                        }
                    ]
                }
            }

    def fake_create_agent(*, model, tools, system_prompt, response_format):
        assert model.__class__.__name__ == "ModelProviderChatModel"
        assert tools == []
        assert response_format["type"] == "json_schema"
        return FakeCompiledAgent()

    import langchain.agents

    monkeypatch.setattr(langchain.agents, "create_agent", fake_create_agent)

    mappings = await knowledge_update._run_step_four_router_agent(
        step_one_graph_delta={"blocks": [{"id": "block-1", "properties": [{"key": "text", "string_value": "Alice"}]}]},
        step_three_graph_delta={"entities": [{"id": "entity-1", "properties": [{"key": "name", "string_value": "Alice"}]}]},
        settings=Settings(model_provider_base_url="http://provider"),
    )

    assert mappings == [
        {
            "block_id": "block-1",
            "entity_id": "entity-1",
            "confidence": 0.95,
            "reason": "explicit mention",
        }
    ]
