from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.services.job_orchestrator_client import JobOrchestratorClient


class _FakeChannel:
    def __init__(self, target: str) -> None:
        self.target = target
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class _FakeStub:
    def __init__(self, channel: _FakeChannel) -> None:
        self.channel = channel
        self.requests = []

    async def EnqueueJob(self, request, timeout=None):  # noqa: N802 - gRPC method name
        self.requests.append((request, timeout))
        return SimpleNamespace(job_id="job-123")


@pytest.mark.asyncio
async def test_enqueue_job_builds_typed_knowledge_update_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    created_channels: list[_FakeChannel] = []
    created_stubs: list[_FakeStub] = []

    def _fake_channel_factory(target: str) -> _FakeChannel:
        channel = _FakeChannel(target)
        created_channels.append(channel)
        return channel

    def _fake_stub_factory(channel: _FakeChannel) -> _FakeStub:
        stub = _FakeStub(channel)
        created_stubs.append(stub)
        return stub

    monkeypatch.setattr("app.services.job_orchestrator_client.grpc.aio.insecure_channel", _fake_channel_factory)
    monkeypatch.setattr("app.services.job_orchestrator_client.job_orchestrator_pb2_grpc.JobOrchestratorStub", _fake_stub_factory)

    client = JobOrchestratorClient(grpc_target="localhost:50061")

    job_id = await client.enqueue_job(
        user_id="user-1",
        job_type="knowledge.update",
        payload={
            "journal_reference": "2026/02/19",
            "messages": [{"role": "user", "content": "hello", "sequence": 1}],
            "requested_by_user_id": "user-1",
        },
    )

    assert job_id == "job-123"
    assert len(created_channels) == 1
    assert created_channels[0].target == "localhost:50061"
    request, timeout = created_stubs[0].requests[0]
    assert request.job_type == "knowledge.update"
    assert request.user_id == "user-1"
    assert request.WhichOneof("payload") == "knowledge_update"
    assert request.knowledge_update.requested_by_user_id == "user-1"
    assert request.knowledge_update.messages[0].sequence == 1
    assert timeout == 5.0


@pytest.mark.asyncio
async def test_enqueue_job_builds_json_payload_for_non_typed_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    created_stubs: list[_FakeStub] = []

    monkeypatch.setattr(
        "app.services.job_orchestrator_client.grpc.aio.insecure_channel",
        lambda target: _FakeChannel(target),
    )

    def _fake_stub_factory(channel: _FakeChannel) -> _FakeStub:
        stub = _FakeStub(channel)
        created_stubs.append(stub)
        return stub

    monkeypatch.setattr("app.services.job_orchestrator_client.job_orchestrator_pb2_grpc.JobOrchestratorStub", _fake_stub_factory)

    client = JobOrchestratorClient(grpc_target="localhost:50061")

    await client.enqueue_job(user_id="user-1", job_type="other.job", payload={"a": 1})

    request, _ = created_stubs[0].requests[0]
    assert request.user_id == "user-1"
    assert request.WhichOneof("payload") == "payload_json"
    assert json.loads(request.payload_json)["a"] == 1


@pytest.mark.asyncio
async def test_close_closes_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = _FakeChannel("localhost:50061")
    monkeypatch.setattr("app.services.job_orchestrator_client.grpc.aio.insecure_channel", lambda _target: channel)
    monkeypatch.setattr("app.services.job_orchestrator_client.job_orchestrator_pb2_grpc.JobOrchestratorStub", _FakeStub)

    client = JobOrchestratorClient(grpc_target="localhost:50061")
    await client.enqueue_job(user_id="user-1", job_type="other.job", payload={"a": 1})
    await client.close()

    assert channel.closed is True


@pytest.mark.asyncio
async def test_enqueue_job_uses_custom_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    created_stubs: list[_FakeStub] = []

    monkeypatch.setattr(
        "app.services.job_orchestrator_client.grpc.aio.insecure_channel",
        lambda target: _FakeChannel(target),
    )

    def _fake_stub_factory(channel: _FakeChannel) -> _FakeStub:
        stub = _FakeStub(channel)
        created_stubs.append(stub)
        return stub

    monkeypatch.setattr("app.services.job_orchestrator_client.job_orchestrator_pb2_grpc.JobOrchestratorStub", _fake_stub_factory)

    client = JobOrchestratorClient(grpc_target="localhost:50061", connect_timeout_seconds=2.5)
    await client.enqueue_job(user_id="user-1", job_type="other.job", payload={"a": 1})

    _, timeout = created_stubs[0].requests[0]
    assert timeout == 2.5
