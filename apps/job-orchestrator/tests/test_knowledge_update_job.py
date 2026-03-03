from __future__ import annotations

import logging

import pytest

from app.contracts import KnowledgeUpdatePayload
from app.services.grpc import knowledge_pb2
from app.worker.jobs.knowledge_update import (
    _build_batch_document,
    _build_upsert_graph_delta_step_one,
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
content:
"""


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
