from __future__ import annotations

import socket

import grpc
import pytest

from app.contracts import JobEnvelope
from app.services.grpc import knowledge_pb2
from app.worker.process_runner import LocalProcessWorkerRunner


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.asyncio
async def test_process_runner_surfaces_worker_error_for_incomplete_grpc_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = grpc.aio.server()

    async def get_user_init_graph(request: knowledge_pb2.GetUserInitGraphRequest, context) -> knowledge_pb2.GetUserInitGraphReply:
        return knowledge_pb2.GetUserInitGraphReply(
            person_entity_id=f"person:{request.user_id}",
            assistant_entity_id="assistant:knowledge-interface",
        )

    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "exobrain.knowledge.v1.KnowledgeInterface",
                {
                    "GetUserInitGraph": grpc.unary_unary_rpc_method_handler(
                        get_user_init_graph,
                        request_deserializer=knowledge_pb2.GetUserInitGraphRequest.FromString,
                        response_serializer=knowledge_pb2.GetUserInitGraphReply.SerializeToString,
                    )
                },
            ),
        )
    )

    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    monkeypatch.setenv("KNOWLEDGE_INTERFACE_GRPC_TARGET", f"127.0.0.1:{port}")
    monkeypatch.setenv("KNOWLEDGE_INTERFACE_CONNECT_TIMEOUT_SECONDS", "1")

    job = JobEnvelope(
        job_type="knowledge.update",
        correlation_id="user-1",
        payload={
            "journal_reference": "2026/02/24",
            "messages": [{"role": "user", "content": "hello", "created_at": "2026-02-24T00:00:00Z"}],
            "requested_by_user_id": "user-1",
        },
    )

    try:
        runner = LocalProcessWorkerRunner()
        with pytest.raises(RuntimeError) as exc_info:
            await runner.run_job(job)
    finally:
        await server.stop(0)

    assert "Method not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_process_runner_raises_when_target_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KNOWLEDGE_INTERFACE_GRPC_TARGET", f"127.0.0.1:{_free_port()}")
    monkeypatch.setenv("KNOWLEDGE_INTERFACE_CONNECT_TIMEOUT_SECONDS", "0.1")

    job = JobEnvelope(
        job_type="knowledge.update",
        correlation_id="user-1",
        payload={
            "journal_reference": "2026/02/24",
            "messages": [{"role": "user", "content": "hello", "created_at": "2026-02-24T00:00:00Z"}],
            "requested_by_user_id": "user-1",
        },
    )

    runner = LocalProcessWorkerRunner()
    with pytest.raises(RuntimeError) as exc_info:
        await runner.run_job(job)

    assert "knowledge-interface connection timed out" in str(exc_info.value)
    assert "Traceback" in str(exc_info.value)
