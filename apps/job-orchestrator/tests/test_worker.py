from __future__ import annotations

import json

import pytest

from app.contracts import JobEnvelope
from app.orchestrator import JobOrchestrator


class FakeRepo:
    def __init__(self, inserted: bool = True) -> None:
        self.inserted = inserted
        self.calls: list[tuple[str, str]] = []

    async def register_requested(self, job: JobEnvelope) -> bool:
        self.calls.append(("register", job.job_id))
        return self.inserted

    async def mark_processing(self, job_id: str, attempt: int) -> None:
        self.calls.append(("processing", f"{job_id}:{attempt}"))

    async def mark_completed(self, job_id: str) -> None:
        self.calls.append(("completed", job_id))

    async def mark_failed(self, job_id: str, error_message: str) -> None:
        self.calls.append(("failed", job_id))


class FakeRunner:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    async def run_job(self, _: JobEnvelope) -> None:
        if self.should_fail:
            raise RuntimeError("boom")


class FakeMsg:
    def __init__(self, payload: dict[str, object] | None = None, *, raw_data: bytes | None = None) -> None:
        self.data = raw_data if raw_data is not None else json.dumps(payload or {}).encode("utf-8")
        self.acked = False

    async def ack(self) -> None:
        self.acked = True


@pytest.mark.asyncio
async def test_worker_marks_completed_for_new_job() -> None:
    events: list[str] = []

    async def publish(subject: str, _: bytes) -> None:
        events.append(subject)

    repo = FakeRepo(inserted=True)
    worker = JobOrchestrator(
        repository=repo,
        runner=FakeRunner(),
        events_subject_prefix="jobs.events",
        publish_event=publish,
    )

    payload = {
        "job_id": "job-1",
        "job_type": "knowledge.update",
        "correlation_id": "corr-1",
        "payload": {"messages": ["note"]},
        "attempt": 0,
    }

    msg = FakeMsg(payload)
    await worker.process_message(msg)

    assert msg.acked is True
    assert ("completed", "job-1") in repo.calls
    assert events == ["jobs.events.knowledge.update.completed"]


@pytest.mark.asyncio
async def test_worker_accepts_legacy_envelope_without_payload() -> None:
    events: list[str] = []

    async def publish(subject: str, _: bytes) -> None:
        events.append(subject)

    repo = FakeRepo(inserted=True)
    worker = JobOrchestrator(
        repository=repo,
        runner=FakeRunner(),
        events_subject_prefix="jobs.events",
        publish_event=publish,
    )

    msg = FakeMsg(
        {
            "job_id": "job-legacy",
            "job_type": "knowledge.update",
            "correlation_id": "corr-1",
            "attempt": 0,
        }
    )

    await worker.process_message(msg)

    assert msg.acked is True
    assert ("completed", "job-legacy") in repo.calls
    assert events == ["jobs.events.knowledge.update.completed"]


@pytest.mark.asyncio
async def test_worker_drops_invalid_envelope_and_acks() -> None:
    async def publish(_: str, __: bytes) -> None:
        return None

    repo = FakeRepo(inserted=True)
    worker = JobOrchestrator(
        repository=repo,
        runner=FakeRunner(),
        events_subject_prefix="jobs.events",
        publish_event=publish,
    )
    msg = FakeMsg(raw_data=b"not-json")

    await worker.process_message(msg)

    assert msg.acked is True
    assert repo.calls == []


@pytest.mark.asyncio
async def test_worker_skips_duplicate_job() -> None:
    async def publish(_: str, __: bytes) -> None:
        return None

    repo = FakeRepo(inserted=False)
    worker = JobOrchestrator(
        repository=repo,
        runner=FakeRunner(),
        events_subject_prefix="jobs.events",
        publish_event=publish,
    )
    msg = FakeMsg(
        {
            "job_id": "job-duplicate",
            "job_type": "knowledge.update",
            "correlation_id": "corr-1",
            "payload": {},
            "attempt": 0,
        }
    )

    await worker.process_message(msg)

    assert msg.acked is True
    assert repo.calls == [("register", "job-duplicate")]
