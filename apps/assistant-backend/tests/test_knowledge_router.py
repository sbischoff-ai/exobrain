from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.dependencies.auth import get_required_auth_context
from app.api.routers import knowledge as knowledge_router
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.knowledge import KnowledgeUpdateRequest
from app.services.contracts import KnowledgeServiceProtocol
from tests.conftest import build_test_container, build_test_request


class FakeKnowledgeService:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | None]] = []

    async def enqueue_update_job(self, *, user_id: str, journal_reference: str | None = None) -> str:
        self.calls.append({"user_id": user_id, "journal_reference": journal_reference})
        return "job-knowledge-1"


@pytest.mark.asyncio
async def test_enqueue_knowledge_update_uses_knowledge_service_with_reference() -> None:
    principal = UnifiedPrincipal(user_id="user-1", email="u@example.com", display_name="User")
    service = FakeKnowledgeService()
    container = build_test_container({KnowledgeServiceProtocol: service})
    request = build_test_request(container)

    response = await knowledge_router.enqueue_knowledge_update(
        payload=KnowledgeUpdateRequest(journal_reference="2026/02/19"),
        request=request,
        auth_context=principal,
    )

    assert response.job_id == "job-knowledge-1"
    assert response.status == "queued"
    assert service.calls == [{"user_id": "user-1", "journal_reference": "2026/02/19"}]


@pytest.mark.asyncio
async def test_enqueue_knowledge_update_uses_knowledge_service_without_reference() -> None:
    principal = UnifiedPrincipal(user_id="user-1", email="u@example.com", display_name="User")
    service = FakeKnowledgeService()
    container = build_test_container({KnowledgeServiceProtocol: service})
    request = build_test_request(container)

    response = await knowledge_router.enqueue_knowledge_update(
        payload=KnowledgeUpdateRequest(),
        request=request,
        auth_context=principal,
    )

    assert response.job_id == "job-knowledge-1"
    assert response.status == "queued"
    assert service.calls == [{"user_id": "user-1", "journal_reference": None}]


def test_api_knowledge_update_surfaces_job_id() -> None:
    principal = UnifiedPrincipal(user_id="user-1", email="u@example.com", display_name="User")
    service = FakeKnowledgeService()
    container = build_test_container({KnowledgeServiceProtocol: service})

    app = FastAPI()

    @app.middleware("http")
    async def attach_container(request, call_next):
        request.app.state.container = container
        return await call_next(request)

    app.dependency_overrides[get_required_auth_context] = lambda: principal
    app.include_router(knowledge_router.router, prefix="/api")

    with TestClient(app) as client:
        response = client.post("/api/knowledge/update", json={"journal_reference": "2026/02/19"})

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-knowledge-1"
    assert service.calls == [{"user_id": "user-1", "journal_reference": "2026/02/19"}]
