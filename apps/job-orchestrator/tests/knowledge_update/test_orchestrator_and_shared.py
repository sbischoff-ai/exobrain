from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.grpc import knowledge_pb2
from app.worker.jobs.knowledge_update import (
    KnowledgeUpdateStepError,
    _call_with_retry,
    _format_exception_for_stderr,
    _validate_upsert_graph_delta_payload,
    run,
)


def test_format_exception_for_stderr_includes_traceback_and_message() -> None:
    try:
        raise ValueError("boom")
    except ValueError as exc:
        formatted = _format_exception_for_stderr(exc)
    assert "ValueError: boom" in formatted


@pytest.mark.asyncio
async def test_call_with_retry_wraps_failure_with_step_metadata() -> None:
    async def non_transient_call() -> None:
        raise ValueError("bad input")

    with pytest.raises(KnowledgeUpdateStepError):
        await _call_with_retry(step_name="step y", operation="op", call=non_transient_call)


def test_validate_upsert_graph_delta_payload_reports_invalid_field_path() -> None:
    with pytest.raises(RuntimeError):
        _validate_upsert_graph_delta_payload("step nine", {"entities": [{"id": "entity-1", "type_id": "node.person", "user_id": "user-1", "visibility": "PRIVATE", "properties": [{"key": "name", "string_value": "Alice", "invalid_field": "nope"}]}]})


class _FakeGrpcChannelContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def channel_ready(self) -> None:
        return None

    def unary_unary(self, method: str, request_serializer, response_deserializer):
        async def _call(request):
            return knowledge_pb2.UpsertGraphDeltaReply(entities_upserted=1, blocks_upserted=1, edges_upserted=1)

        return _call


@pytest.mark.asyncio
async def test_call_with_retry_includes_http_response_body_in_error_detail() -> None:
    class _FakeResponse:
        status_code = 400

        @property
        def text(self) -> str:
            return '{"error":"invalid schema"}'

    class _FakeHTTPStatusError(Exception):
        def __init__(self) -> None:
            super().__init__(
                "Client error '400 Bad Request' for url "
                "'http://localhost:8010/v1/internal/chat/messages'"
            )
            self.response = _FakeResponse()

    async def http_error_call() -> None:
        raise _FakeHTTPStatusError()

    with pytest.raises(KnowledgeUpdateStepError) as exc_info:
        await _call_with_retry(
            step_name="step six",
            operation="relationship_extraction_agent.ainvoke",
            call=http_error_call,
        )

    message = str(exc_info.value)
    assert "status_code=400" in message
    assert 'response_body={"error":"invalid schema"}' in message

@pytest.mark.asyncio
async def test_call_with_retry_retries_transient_connect_error_to_max_attempts() -> None:
    attempts = 0

    class ConnectError(Exception):
        pass

    async def flaky_call() -> str:
        nonlocal attempts
        attempts += 1
        raise ConnectError("connection failed")

    with pytest.raises(KnowledgeUpdateStepError):
        await _call_with_retry(
            step_name="step connect",
            operation="agent.ainvoke",
            call=flaky_call,
            max_attempts=3,
            base_delay_seconds=0.0,
            max_delay_seconds=0.0,
        )

    assert attempts == 3


@pytest.mark.asyncio
async def test_call_with_retry_fails_fast_for_non_transient_error() -> None:
    attempts = 0

    async def non_transient_call() -> None:
        nonlocal attempts
        attempts += 1
        raise ValueError("bad input")

    with pytest.raises(KnowledgeUpdateStepError):
        await _call_with_retry(
            step_name="step non transient",
            operation="agent.ainvoke",
            call=non_transient_call,
            max_attempts=5,
            base_delay_seconds=0.0,
            max_delay_seconds=0.0,
        )

    assert attempts == 1


@pytest.mark.asyncio
async def test_run_fails_fast_with_step_specific_parse_dict_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.worker.jobs.knowledge_update as knowledge_update
    from app.worker.jobs.knowledge_update.types import EntityExtractionResult

    job = SimpleNamespace(payload={"journal_reference": "journal-1", "requested_by_user_id": "user-1", "messages": [{"role": "user", "content": "hello", "created_at": "2026-03-02T12:00:00Z"}]})
    invalid_graph = {"entities": [{"id": "entity-1", "type_id": "node.person", "user_id": "user-1", "visibility": "PRIVATE", "properties": [{"key": "name", "string_value": "Alice", "invalid_field": "bad"}]}], "blocks": [], "edges": [], "universes": []}

    async def fake_step02(*_args, **_kwargs):
        return EntityExtractionResult.model_validate({"extracted_entities": [], "extracted_universes": []})

    async def fake_step03(*_args, **_kwargs):
        return []

    async def fake_step04(*_args, **_kwargs):
        return []

    async def fake_step05(*_args, **_kwargs):
        return []

    async def fake_step06(*_args, **_kwargs):
        return []

    async def fake_step07(*_args, **_kwargs):
        return []

    async def fake_step08(*_args, **_kwargs):
        return []

    def fake_step09(*_args, **_kwargs):
        return invalid_graph

    monkeypatch.setattr(knowledge_update.step02_entity_extraction, "run", fake_step02)
    monkeypatch.setattr(knowledge_update.step03_candidate_matching, "run", fake_step03)
    monkeypatch.setattr(knowledge_update.step04_entity_context, "run", fake_step04)
    monkeypatch.setattr(knowledge_update.step05_entity_resolution, "run", fake_step05)
    monkeypatch.setattr(knowledge_update.step06_relationship_extraction, "run", fake_step06)
    monkeypatch.setattr(knowledge_update.step07_relationship_match, "run", fake_step07)
    monkeypatch.setattr(knowledge_update.step08_entity_graph, "run", fake_step08)
    monkeypatch.setattr(knowledge_update.step09_merge_graph, "run", fake_step09)
    monkeypatch.setattr(knowledge_update, "get_settings", lambda: SimpleNamespace(knowledge_interface_grpc_target="localhost:50051", knowledge_interface_connect_timeout_seconds=0.1))
    monkeypatch.setattr(knowledge_update.grpc.aio, "insecure_channel", lambda _target: _FakeGrpcChannelContext())

    with pytest.raises(RuntimeError):
        await run(job)
