from __future__ import annotations

import json
from types import SimpleNamespace

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

    async def mark_retrying_failure(self, job_id: str, error_message: str) -> None:
        self.calls.append(("retrying_failed", job_id))

    async def mark_terminal_failure(self, job_id: str, error_message: str, terminal_reason: str) -> None:
        self.calls.append(("terminal_failed", f"{job_id}:{terminal_reason}"))


class FakeRunner:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    async def run_job(self, _: JobEnvelope) -> None:
        if self.should_fail:
            raise RuntimeError("boom")


class FakeMsg:
    def __init__(self, payload: dict[str, object] | None = None, *, raw_data: bytes | None = None, delivery_attempt: int = 1, subject: str = "jobs.knowledge.update.requested") -> None:
        self.data = raw_data if raw_data is not None else json.dumps(payload or {}).encode("utf-8")
        self.metadata = SimpleNamespace(num_delivered=delivery_attempt)
        self.subject = subject
        self.acked = False
        self.nacked = False

    async def ack(self) -> None:
        self.acked = True

    async def nak(self) -> None:
        self.nacked = True


def _build_worker(repo: FakeRepo, runner: FakeRunner, publish):
    return JobOrchestrator(
        repository=repo,
        runner=runner,
        events_subject_prefix="jobs.events",
        dlq_subject="jobs.dlq",
        max_attempts=3,
        dlq_raw_message_max_chars=128,
        publish_event=publish,
    )


def _valid_payload(job_id: str = "job-1") -> dict[str, object]:
    return {
        "job_id": job_id,
        "job_type": "knowledge.update",
        "correlation_id": "corr-1",
        "payload": {
            "journal_reference": "2026/02/24",
            "messages": [{"role": "user", "content": "hello"}],
            "requested_by_user_id": "user-1",
        },
        "attempt": 0,
    }


@pytest.mark.asyncio
async def test_worker_marks_completed_for_new_job() -> None:
    events: list[str] = []

    async def publish(subject: str, _: bytes) -> None:
        events.append(subject)

    repo = FakeRepo(inserted=True)
    worker = _build_worker(repo, FakeRunner(), publish)

    msg = FakeMsg(_valid_payload())
    await worker.process_message(msg)

    assert msg.acked is True
    assert msg.nacked is False
    assert ("completed", "job-1") in repo.calls
    assert events == [
        "jobs.status.job-1",
        "jobs.status.job-1",
        "jobs.events.knowledge.update.completed",
        "jobs.status.job-1",
    ]


@pytest.mark.asyncio
async def test_worker_retries_invalid_envelope_before_dlq() -> None:
    events: list[str] = []

    async def publish(subject: str, _: bytes) -> None:
        events.append(subject)

    repo = FakeRepo(inserted=True)
    worker = _build_worker(repo, FakeRunner(), publish)
    msg = FakeMsg(raw_data=b"not-json", delivery_attempt=1)

    await worker.process_message(msg)

    assert msg.acked is False
    assert msg.nacked is True
    assert repo.calls == []
    assert events == []


@pytest.mark.asyncio
async def test_worker_dlqs_invalid_envelope_at_max_attempts() -> None:
    events: list[str] = []

    async def publish(subject: str, _: bytes) -> None:
        events.append(subject)

    repo = FakeRepo(inserted=True)
    worker = _build_worker(repo, FakeRunner(), publish)
    msg = FakeMsg(raw_data=b"not-json", delivery_attempt=3)

    await worker.process_message(msg)

    assert msg.acked is True
    assert msg.nacked is False
    assert repo.calls == []
    assert events == ["jobs.dlq"]


@pytest.mark.asyncio
async def test_worker_acks_even_if_dlq_publish_fails() -> None:
    async def publish(_: str, __: bytes) -> None:
        raise RuntimeError("publish failed")

    repo = FakeRepo(inserted=True)
    worker = _build_worker(repo, FakeRunner(), publish)
    msg = FakeMsg(raw_data=b"not-json", delivery_attempt=3)

    await worker.process_message(msg)

    assert msg.acked is True


@pytest.mark.asyncio
async def test_worker_sends_invalid_payload_to_dlq_and_acks() -> None:
    events: list[str] = []

    async def publish(subject: str, _: bytes) -> None:
        events.append(subject)

    repo = FakeRepo(inserted=True)
    worker = _build_worker(repo, FakeRunner(), publish)
    bad = _valid_payload()
    bad["payload"] = {"journal_reference": "2026/02/24"}
    msg = FakeMsg(bad)

    await worker.process_message(msg)

    assert msg.acked is True
    assert repo.calls == []
    assert events == ["jobs.dlq"]


@pytest.mark.asyncio
async def test_worker_naks_on_retryable_failure() -> None:
    events: list[str] = []

    async def publish(subject: str, _: bytes) -> None:
        events.append(subject)

    repo = FakeRepo(inserted=True)
    worker = _build_worker(repo, FakeRunner(should_fail=True), publish)
    msg = FakeMsg(_valid_payload(), delivery_attempt=1)

    await worker.process_message(msg)

    assert msg.acked is False
    assert msg.nacked is True
    assert ("retrying_failed", "job-1") in repo.calls
    assert events == ["jobs.status.job-1", "jobs.status.job-1", "jobs.status.job-1"]


@pytest.mark.asyncio
async def test_worker_dlqs_when_max_attempts_reached() -> None:
    events: list[str] = []

    async def publish(subject: str, _: bytes) -> None:
        events.append(subject)

    repo = FakeRepo(inserted=True)
    worker = _build_worker(repo, FakeRunner(should_fail=True), publish)
    msg = FakeMsg(_valid_payload(), delivery_attempt=3)

    await worker.process_message(msg)

    assert msg.acked is True
    assert msg.nacked is False
    assert ("terminal_failed", "job-1:max-attempts") in repo.calls
    assert events == [
        "jobs.status.job-1",
        "jobs.events.knowledge.update.failed",
        "jobs.status.job-1",
        "jobs.dlq",
    ]


@pytest.mark.asyncio
async def test_worker_ignores_non_requested_subject() -> None:
    events: list[str] = []

    async def publish(subject: str, _: bytes) -> None:
        events.append(subject)

    repo = FakeRepo(inserted=True)
    worker = _build_worker(repo, FakeRunner(), publish)
    msg = FakeMsg(_valid_payload(), subject="jobs.dlq")

    await worker.process_message(msg)

    assert msg.acked is True
    assert msg.nacked is False
    assert repo.calls == []
    assert events == []


@pytest.mark.asyncio
async def test_worker_skips_duplicate_first_delivery() -> None:
    async def publish(_: str, __: bytes) -> None:
        return None

    repo = FakeRepo(inserted=False)
    worker = _build_worker(repo, FakeRunner(), publish)
    msg = FakeMsg(_valid_payload(job_id="job-duplicate"), delivery_attempt=1)

    await worker.process_message(msg)

    assert msg.acked is True
    assert repo.calls == [("register", "job-duplicate")]
