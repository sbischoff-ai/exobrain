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
async def test_run_fails_fast_with_step_specific_parse_dict_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.worker.jobs.knowledge_update as knowledge_update

    job = SimpleNamespace(payload={"journal_reference": "journal-1", "requested_by_user_id": "user-1", "messages": [{"role": "user", "content": "hello", "created_at": "2026-03-02T12:00:00Z"}]})
    invalid_graph = {"entities": [{"id": "entity-1", "type_id": "node.person", "user_id": "user-1", "visibility": "PRIVATE", "properties": [{"key": "name", "string_value": "Alice", "invalid_field": "bad"}]}], "blocks": [], "edges": [], "universes": []}
    async def fake_step01(*_args, **_kwargs):
        return invalid_graph

    monkeypatch.setattr(knowledge_update.step01_graph_seed, "run", fake_step01)
    monkeypatch.setattr(knowledge_update, "get_settings", lambda: SimpleNamespace(knowledge_interface_grpc_target="localhost:50051", knowledge_interface_connect_timeout_seconds=0.1))
    monkeypatch.setattr(knowledge_update.grpc.aio, "insecure_channel", lambda _target: _FakeGrpcChannelContext())

    with pytest.raises(RuntimeError):
        await run(job)
