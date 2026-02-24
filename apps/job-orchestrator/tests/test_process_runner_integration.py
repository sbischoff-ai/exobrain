from __future__ import annotations

import asyncio
import socket

import grpc
import pytest

from app.contracts import JobEnvelope
from app.worker.process_runner import LocalProcessWorkerRunner


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.asyncio
async def test_process_runner_executes_knowledge_update_job(monkeypatch: pytest.MonkeyPatch) -> None:
    server = grpc.aio.server()
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    monkeypatch.setenv("KNOWLEDGE_INTERFACE_GRPC_TARGET", f"127.0.0.1:{port}")
    monkeypatch.setenv("KNOWLEDGE_INTERFACE_CONNECT_TIMEOUT_SECONDS", "1")

    job = JobEnvelope(
        job_type="knowledge.update",
        correlation_id="user-1",
        payload={
            "journal_reference": "2026/02/24",
            "messages": [{"role": "user", "content": "hello"}],
            "requested_by_user_id": "user-1",
        },
    )

    try:
        runner = LocalProcessWorkerRunner()
        await runner.run_job(job)
    finally:
        await server.stop(0)


@pytest.mark.asyncio
async def test_process_runner_raises_when_target_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KNOWLEDGE_INTERFACE_GRPC_TARGET", f"127.0.0.1:{_free_port()}")
    monkeypatch.setenv("KNOWLEDGE_INTERFACE_CONNECT_TIMEOUT_SECONDS", "0.1")

    job = JobEnvelope(
        job_type="knowledge.update",
        correlation_id="user-1",
        payload={
            "journal_reference": "2026/02/24",
            "messages": [{"role": "user", "content": "hello"}],
            "requested_by_user_id": "user-1",
        },
    )

    runner = LocalProcessWorkerRunner()
    with pytest.raises(RuntimeError):
        await runner.run_job(job)
