from __future__ import annotations

import pytest

from app.api.routers import jobs as jobs_router
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.jobs import CreateKnowledgeJobRequest
from app.services.contracts import JobPublisherProtocol
from tests.conftest import build_test_container, build_test_request


class FakeJobPublisher:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def enqueue_job(self, *, job_type: str, correlation_id: str, payload: dict[str, object]) -> str:
        self.calls.append(
            {
                "job_type": job_type,
                "correlation_id": correlation_id,
                "payload": payload,
            }
        )
        return "job-123"


@pytest.mark.asyncio
async def test_enqueue_knowledge_job_uses_job_publisher() -> None:
    principal = UnifiedPrincipal(user_id="user-1", email="u@example.com", display_name="User")
    publisher = FakeJobPublisher()
    container = build_test_container({JobPublisherProtocol: publisher})
    request = build_test_request(container)

    response = await jobs_router.enqueue_knowledge_job(
        payload=CreateKnowledgeJobRequest(operation="ingest", reference="2026/02/19", metadata={"source": "journal"}),
        request=request,
        auth_context=principal,
    )

    assert response.job_id == "job-123"
    assert response.status == "queued"
    assert publisher.calls[0]["job_type"] == "knowledge.ingest"
    assert publisher.calls[0]["correlation_id"] == "user-1"
