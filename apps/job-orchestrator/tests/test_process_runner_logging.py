from __future__ import annotations

import asyncio
import logging

import pytest

from app.contracts import JobEnvelope
from app.worker.process_runner import LocalProcessWorkerRunner


class _FakeProcess:
    returncode = 0

    async def communicate(self):
        return b"", b""


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
