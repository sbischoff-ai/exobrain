from __future__ import annotations

import logging

import pytest

from app.contracts import KnowledgeUpdatePayload
from app.services.grpc import knowledge_pb2
from app.worker.jobs.knowledge_update import (
    _build_batch_document,
    _build_step_two_entity_extraction_json_schema,
    _build_step_two_entity_extraction_system_prompt,
    _run_step_two_entity_extraction,
    _step_two_store_batch_document,
)


class FakeEntityExtractionChannel:
    def unary_unary(self, method: str, request_serializer, response_deserializer):
        async def _call(request):
            assert request.user_id == "user-1"
            if method.endswith("/GetEntityExtractionSchemaContext"):
                return knowledge_pb2.GetEntityExtractionSchemaContextReply()
            raise AssertionError(method)

        return _call


def test_build_batch_document_formats_header_and_turns() -> None:
    payload = KnowledgeUpdatePayload(journal_reference="journal-1", requested_by_user_id="user-1", messages=[{"role": "assistant", "content": "hi", "sequence": 7, "created_at": "2026-03-02T12:00:00Z"}])
    assert _build_batch_document(payload).startswith("=== BATCH DOCUMENT ===")


def test_step02_schema_and_prompt() -> None:
    schema = _build_step_two_entity_extraction_json_schema()
    assert schema["required"] == ["extracted_entities", "extracted_universes"]
    prompt = _build_step_two_entity_extraction_system_prompt({"entity_types": [{"type_id": "node.person"}]})
    assert "node.person" in prompt


def test_step02_logs_batch_document(caplog: pytest.LogCaptureFixture) -> None:
    payload = KnowledgeUpdatePayload(journal_reference="journal-1", requested_by_user_id="user-1", messages=[{"role": "user", "content": "hello"}])
    with caplog.at_level(logging.INFO):
        _step_two_store_batch_document(payload)
    assert "knowledge.update step one batch document" in caplog.text


@pytest.mark.asyncio
async def test_run_step02_entity_extraction_uses_worker_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings import Settings
    import langchain.agents

    class FakeCompiledAgent:
        async def ainvoke(self, payload: dict[str, object]) -> dict[str, object]:
            return {"structured_response": {"extracted_entities": [{"name": "Alice", "node_type": "node.person", "aliases": [], "short_description": "A person"}], "extracted_universes": []}}

    monkeypatch.setattr(langchain.agents, "create_agent", lambda **kwargs: FakeCompiledAgent())
    payload = KnowledgeUpdatePayload(journal_reference="journal-1", requested_by_user_id="user-1", messages=[{"role": "user", "content": "hello", "created_at": "2026-03-02T12:00:00Z"}])
    result = await _run_step_two_entity_extraction(FakeEntityExtractionChannel(), payload, "--- TURN 1 ---", Settings(model_provider_base_url="http://provider", knowledge_update_extraction_model="worker"))
    assert result.extracted_entities[0].name == "Alice"
