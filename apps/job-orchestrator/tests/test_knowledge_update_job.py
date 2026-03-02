from __future__ import annotations

import logging

import pytest

from app.contracts import KnowledgeUpdatePayload
from app.services.grpc import knowledge_pb2
from app.worker.jobs.knowledge_update import _build_upsert_graph_delta_step_one, _step_two_placeholder_log


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


def test_step_two_logs_placeholder_request(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        _step_two_placeholder_log({"entities": []})

    assert "knowledge.update step two placeholder" in caplog.text
