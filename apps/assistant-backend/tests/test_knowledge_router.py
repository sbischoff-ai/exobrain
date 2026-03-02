from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from app.api.dependencies.auth import get_required_auth_context
from app.api.routers import knowledge as knowledge_router
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.knowledge import KnowledgeUpdateRequest
from app.services.contracts import KnowledgeServiceProtocol
from app.services.knowledge_service import (
    KnowledgeJobAccessDeniedError,
    KnowledgeJobNotFoundError,
    KnowledgeUpstreamUnavailableError,
    KnowledgeWatchError,
)
from tests.conftest import build_test_container, build_test_request


class FakeKnowledgeService:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | None]] = []
        self.watch_calls: list[dict[str, object]] = []

    async def enqueue_update_job(self, *, user_id: str, journal_reference: str | None = None) -> str:
        self.calls.append({"user_id": user_id, "journal_reference": journal_reference})
        return "job-knowledge-1"

    async def watch_update_job(
        self,
        *,
        user_id: str,
        job_id: str,
        include_current: bool = True,
    ) -> AsyncIterator[dict[str, object]]:
        self.watch_calls.append({"user_id": user_id, "job_id": job_id, "include_current": include_current})
        yield {"type": "status", "data": {"job_id": job_id, "state": "STARTED", "attempt": 1, "detail": "working", "terminal": False, "emitted_at": "2026-02-19T10:00:00Z"}}
        yield {"type": "done", "data": {"job_id": job_id, "state": "SUCCEEDED", "terminal": True}}


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


def test_api_knowledge_watch_streams_sse_events() -> None:
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
        response = client.get("/api/knowledge/update/job-knowledge-1/watch")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: status" in response.text
    assert '"state": "STARTED"' in response.text
    assert "event: done" in response.text
    assert service.watch_calls == [{"user_id": "user-1", "job_id": "job-knowledge-1", "include_current": True}]


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (KnowledgeJobNotFoundError("missing"), 404),
        (KnowledgeJobAccessDeniedError("denied"), 403),
        (KnowledgeUpstreamUnavailableError("unavailable"), 503),
        (KnowledgeWatchError("failed"), 502),
    ],
)
def test_api_knowledge_watch_maps_domain_errors_to_http(error: Exception, expected_status: int) -> None:
    principal = UnifiedPrincipal(user_id="user-1", email="u@example.com", display_name="User")

    class ErroringKnowledgeService(FakeKnowledgeService):
        async def watch_update_job(
            self,
            *,
            user_id: str,
            job_id: str,
            include_current: bool = True,
        ) -> AsyncIterator[dict[str, object]]:
            self.watch_calls.append({"user_id": user_id, "job_id": job_id, "include_current": include_current})
            raise error
            if False:
                yield {"type": "status", "data": {}}

    service = ErroringKnowledgeService()
    container = build_test_container({KnowledgeServiceProtocol: service})

    app = FastAPI()

    @app.middleware("http")
    async def attach_container(request, call_next):
        request.app.state.container = container
        return await call_next(request)

    app.dependency_overrides[get_required_auth_context] = lambda: principal
    app.include_router(knowledge_router.router, prefix="/api")

    with TestClient(app) as client:
        response = client.get("/api/knowledge/update/job-knowledge-1/watch")

    assert response.status_code == expected_status
    assert service.watch_calls == [{"user_id": "user-1", "job_id": "job-knowledge-1", "include_current": True}]


def test_api_knowledge_watch_requires_auth() -> None:
    service = FakeKnowledgeService()
    container = build_test_container({KnowledgeServiceProtocol: service})

    app = FastAPI()

    @app.middleware("http")
    async def attach_container(request, call_next):
        request.app.state.container = container
        return await call_next(request)

    async def deny_auth() -> UnifiedPrincipal:
        raise HTTPException(status_code=401, detail="authentication required")

    app.dependency_overrides[get_required_auth_context] = deny_auth
    app.include_router(knowledge_router.router, prefix="/api")

    with TestClient(app) as client:
        response = client.get("/api/knowledge/update/job-knowledge-1/watch")

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication required"}
    assert service.watch_calls == []
