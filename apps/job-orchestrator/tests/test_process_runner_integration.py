from __future__ import annotations

import asyncio
import socket

import pytest

from app.contracts import JobEnvelope
from app.worker.process_runner import LocalProcessWorkerRunner


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.asyncio
async def test_process_runner_executes_knowledge_update_job(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await reader.read(24)
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle_client, host="127.0.0.1", port=0)
    host, port = server.sockets[0].getsockname()[:2]
    monkeypatch.setenv("KNOWLEDGE_INTERFACE_GRPC_TARGET", f"{host}:{port}")
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
        server.close()
        await server.wait_closed()


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
