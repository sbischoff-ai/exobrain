from __future__ import annotations

import asyncio
import logging

import pytest

from app.contracts import JobEnvelope
from app.worker.process_runner import LocalProcessWorkerRunner


class _FakeProcess:
    def __init__(self, *, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


@pytest.mark.asyncio
async def test_process_runner_debug_logging_does_not_use_reserved_log_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_create_subprocess_exec(*args, **kwargs):
        return _FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    runner = LocalProcessWorkerRunner()
    job = JobEnvelope(
        job_type="knowledge.update",
        correlation_id="user-1",
        payload={
            "journal_reference": "2026/02/24",
            "messages": [{"role": "user", "content": "hello"}],
            "requested_by_user_id": "user-1",
        },
    )

    logging.getLogger("app.worker.process_runner").setLevel(logging.DEBUG)
    await runner.run_job(job)


@pytest.mark.asyncio
async def test_process_runner_logs_worker_stdout_and_stderr(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    async def fake_create_subprocess_exec(*args, **kwargs):
        return _FakeProcess(stdout=b"step-two-log\nstep-three-log\n", stderr=b"minor-warning\n")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    runner = LocalProcessWorkerRunner()
    job = JobEnvelope(
        job_type="knowledge.update",
        correlation_id="user-1",
        payload={
            "journal_reference": "2026/02/24",
            "messages": [{"role": "user", "content": "hello"}],
            "requested_by_user_id": "user-1",
        },
    )

    with caplog.at_level(logging.INFO, logger="app.worker.process_runner"):
        await runner.run_job(job)

    messages = [record.getMessage() for record in caplog.records]
    assert "worker subprocess stdout: step-two-log" in messages
    assert "worker subprocess stdout: step-three-log" in messages
    assert "worker subprocess stderr: minor-warning" in messages


@pytest.mark.asyncio
async def test_process_runner_logs_failed_worker_stderr_at_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def fake_create_subprocess_exec(*args, **kwargs):
        return _FakeProcess(returncode=1, stderr=b"fatal-worker-error\n")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    runner = LocalProcessWorkerRunner()
    job = JobEnvelope(
        job_type="knowledge.update",
        correlation_id="user-1",
        payload={
            "journal_reference": "2026/02/24",
            "messages": [{"role": "user", "content": "hello"}],
            "requested_by_user_id": "user-1",
        },
    )

    with caplog.at_level(logging.INFO, logger="app.worker.process_runner"):
        with pytest.raises(RuntimeError, match="fatal-worker-error"):
            await runner.run_job(job)

    error_records = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert any(record.getMessage() == "worker subprocess stderr: fatal-worker-error" for record in error_records)
