from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from app.api.dependencies.auth import get_required_auth_context
from app.api.routers import knowledge as knowledge_router
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.knowledge import KnowledgeUpdateRequest
from app.services.knowledge_interface_client import (
    KnowledgeInterfaceClientError,
    KnowledgeInterfaceClientInvalidArgumentError,
    KnowledgeInterfaceClientUnavailableError,
)
from app.services.contracts import KnowledgeServiceProtocol
from app.services.knowledge_service import (
    KnowledgeEnqueueError,
    KnowledgeJobAccessDeniedError,
    KnowledgeJobNotFoundError,
    KnowledgeNoPendingMessagesError,
    KnowledgePageAccessDeniedError,
    KnowledgePageNotFoundError,
    KnowledgePageUnavailableError,
    KnowledgePageUpstreamError,
    KnowledgeUpstreamUnavailableError,
    KnowledgeWatchError,
)
from tests.conftest import build_test_container, build_test_request


class FakeKnowledgeService:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | None]] = []
        self.watch_calls: list[dict[str, object]] = []
        self.enqueue_error: Exception | None = None
        self.category_calls: list[dict[str, object]] = []
        self.category_error: Exception | None = None
        self.category_pages_calls: list[dict[str, object]] = []
        self.category_pages_error: Exception | None = None
        self.page_detail_calls: list[dict[str, object]] = []
        self.page_detail_error: Exception | None = None


    async def list_wiki_category_tree(self, *, universe_id: str) -> list[dict[str, object]]:
        self.category_calls.append({"universe_id": universe_id})
        if self.category_error is not None:
            raise self.category_error
        return [
            {
                "category_id": "node.root",
                "display_name": "Root",
                "sub_categories": [
                    {
                        "category_id": "node.child",
                        "display_name": "Child",
                        "sub_categories": [],
                    }
                ],
            }
        ]

    async def list_category_pages(
        self,
        *,
        user_id: str,
        category_id: str,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> dict[str, object]:
        self.category_pages_calls.append(
            {
                "user_id": user_id,
                "category_id": category_id,
                "page_size": page_size,
                "page_token": page_token,
            }
        )
        if self.category_pages_error is not None:
            raise self.category_pages_error
        return {
            "knowledge_pages": [
                {
                    "id": "entity-1",
                    "title": "Entity One",
                    "summary": "Entity summary",
                    "metadata": {
                        "created_at": "",
                        "updated_at": "2026-02-19T10:00:00Z",
                    },
                }
            ],
            "page_size": page_size or 1,
            "next_page_token": "next-token",
            "total_count": 10,
        }

    async def get_page_detail(self, *, user_id: str, page_id: str) -> dict[str, object]:
        self.page_detail_calls.append({"user_id": user_id, "page_id": page_id})
        if self.page_detail_error is not None:
            raise self.page_detail_error
        return {
            "id": page_id,
            "category_id": "node.note",
            "title": "Entity One",
            "summary": "Root",
            "metadata": {
                "created_at": "2026-02-19T09:00:00Z",
                "updated_at": "2026-02-19T10:00:00Z",
            },
            "properties": {"status": "active", "description": "Entity One"},
            "links": [
                {"page_id": "entity-2", "title": "Entity Two", "summary": "Linked"}
            ],
            "content_markdown": "Root\n\nChild",
        }

    async def enqueue_update_job(
        self, *, user_id: str, journal_reference: str | None = None
    ) -> str:
        self.calls.append({"user_id": user_id, "journal_reference": journal_reference})
        if self.enqueue_error is not None:
            raise self.enqueue_error
        return "job-knowledge-1"

    async def watch_update_job(
        self,
        *,
        user_id: str,
        job_id: str,
        include_current: bool = True,
    ) -> AsyncIterator[dict[str, object]]:
        self.watch_calls.append(
            {"user_id": user_id, "job_id": job_id, "include_current": include_current}
        )
        yield {
            "type": "status",
            "data": {
                "job_id": job_id,
                "state": "STARTED",
                "attempt": 1,
                "detail": "working",
                "terminal": False,
                "emitted_at": "2026-02-19T10:00:00Z",
            },
        }
        yield {
            "type": "done",
            "data": {"job_id": job_id, "state": "SUCCEEDED", "terminal": True},
        }


@pytest.mark.asyncio
async def test_enqueue_knowledge_update_uses_knowledge_service_with_reference() -> None:
    principal = UnifiedPrincipal(
        user_id="user-1", email="u@example.com", display_name="User"
    )
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
async def test_enqueue_knowledge_update_uses_knowledge_service_without_reference() -> (
    None
):
    principal = UnifiedPrincipal(
        user_id="user-1", email="u@example.com", display_name="User"
    )
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
    principal = UnifiedPrincipal(
        user_id="user-1", email="u@example.com", display_name="User"
    )
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
        response = client.post(
            "/api/knowledge/update", json={"journal_reference": "2026/02/19"}
        )

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-knowledge-1"
    assert service.calls == [{"user_id": "user-1", "journal_reference": "2026/02/19"}]


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            KnowledgeNoPendingMessagesError("empty"),
            409,
            "no uncommitted messages available for knowledge update",
        ),
        (
            KnowledgeUpstreamUnavailableError("unavailable"),
            503,
            "knowledge update enqueue unavailable",
        ),
        (KnowledgeEnqueueError("failed"), 502, "knowledge update enqueue failed"),
    ],
)
def test_api_knowledge_update_maps_enqueue_domain_errors(
    error: Exception, expected_status: int, expected_detail: str
) -> None:
    principal = UnifiedPrincipal(
        user_id="user-1", email="u@example.com", display_name="User"
    )
    service = FakeKnowledgeService()
    service.enqueue_error = error
    container = build_test_container({KnowledgeServiceProtocol: service})

    app = FastAPI()

    @app.middleware("http")
    async def attach_container(request, call_next):
        request.app.state.container = container
        return await call_next(request)

    app.dependency_overrides[get_required_auth_context] = lambda: principal
    app.include_router(knowledge_router.router, prefix="/api")

    with TestClient(app) as client:
        response = client.post(
            "/api/knowledge/update", json={"journal_reference": "2026/02/19"}
        )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


def test_api_knowledge_watch_streams_sse_events() -> None:
    principal = UnifiedPrincipal(
        user_id="user-1", email="u@example.com", display_name="User"
    )
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
    assert service.watch_calls == [
        {"user_id": "user-1", "job_id": "job-knowledge-1", "include_current": True}
    ]


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (KnowledgeJobNotFoundError("missing"), 404),
        (KnowledgeJobAccessDeniedError("denied"), 403),
        (KnowledgeUpstreamUnavailableError("unavailable"), 503),
        (KnowledgeWatchError("failed"), 502),
    ],
)
def test_api_knowledge_watch_maps_domain_errors_to_http(
    error: Exception, expected_status: int
) -> None:
    principal = UnifiedPrincipal(
        user_id="user-1", email="u@example.com", display_name="User"
    )

    class ErroringKnowledgeService(FakeKnowledgeService):
        async def watch_update_job(
            self,
            *,
            user_id: str,
            job_id: str,
            include_current: bool = True,
        ) -> AsyncIterator[dict[str, object]]:
            self.watch_calls.append(
                {
                    "user_id": user_id,
                    "job_id": job_id,
                    "include_current": include_current,
                }
            )
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
    assert service.watch_calls == [
        {"user_id": "user-1", "job_id": "job-knowledge-1", "include_current": True}
    ]


def test_api_knowledge_category_returns_tree_payload() -> None:
    principal = UnifiedPrincipal(
        user_id="user-1", email="u@example.com", display_name="User"
    )
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
        response = client.get("/api/knowledge/category")

    assert response.status_code == 200
    assert response.json() == {
        "categories": [
            {
                "category_id": "node.root",
                "display_name": "Root",
                "sub_categories": [
                    {
                        "category_id": "node.child",
                        "display_name": "Child",
                        "sub_categories": [],
                    }
                ],
            }
        ]
    }
    assert service.category_calls == [{"universe_id": "wiki"}]


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            KnowledgeInterfaceClientInvalidArgumentError("bad arg"),
            400,
            "invalid knowledge categories request",
        ),
        (
            KnowledgeInterfaceClientUnavailableError("unavailable"),
            503,
            "knowledge categories unavailable",
        ),
        (
            KnowledgeInterfaceClientError("failed"),
            502,
            "knowledge categories upstream failure",
        ),
    ],
)
def test_api_knowledge_category_maps_upstream_errors(
    error: Exception, expected_status: int, expected_detail: str
) -> None:
    principal = UnifiedPrincipal(
        user_id="user-1", email="u@example.com", display_name="User"
    )
    service = FakeKnowledgeService()
    service.category_error = error
    container = build_test_container({KnowledgeServiceProtocol: service})

    app = FastAPI()

    @app.middleware("http")
    async def attach_container(request, call_next):
        request.app.state.container = container
        return await call_next(request)

    app.dependency_overrides[get_required_auth_context] = lambda: principal
    app.include_router(knowledge_router.router, prefix="/api")

    with TestClient(app) as client:
        response = client.get("/api/knowledge/category")

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}



def test_api_knowledge_category_pages_returns_mapped_payload() -> None:
    principal = UnifiedPrincipal(
        user_id="user-1", email="u@example.com", display_name="User"
    )
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
        response = client.get(
            "/api/knowledge/category/type-1/pages?page_size=5&page_token=cursor-1"
        )

    assert response.status_code == 200
    assert response.json()["knowledge_pages"][0]["id"] == "entity-1"
    assert response.json()["knowledge_pages"][0]["metadata"]["updated_at"] == "2026-02-19T10:00:00Z"
    assert service.category_pages_calls == [
        {
            "user_id": "user-1",
            "category_id": "type-1",
            "page_size": 5,
            "page_token": "cursor-1",
        }
    ]


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (KnowledgeInterfaceClientInvalidArgumentError("bad arg"), 400),
        (KnowledgeInterfaceClientUnavailableError("unavailable"), 503),
        (KnowledgeInterfaceClientError("failed"), 502),
    ],
)
def test_api_knowledge_category_pages_maps_upstream_errors(
    error: Exception, expected_status: int
) -> None:
    principal = UnifiedPrincipal(
        user_id="user-1", email="u@example.com", display_name="User"
    )
    service = FakeKnowledgeService()
    service.category_pages_error = error
    container = build_test_container({KnowledgeServiceProtocol: service})

    app = FastAPI()

    @app.middleware("http")
    async def attach_container(request, call_next):
        request.app.state.container = container
        return await call_next(request)

    app.dependency_overrides[get_required_auth_context] = lambda: principal
    app.include_router(knowledge_router.router, prefix="/api")

    with TestClient(app) as client:
        response = client.get("/api/knowledge/category/type-1/pages")

    assert response.status_code == expected_status


def test_api_knowledge_page_returns_mapped_payload() -> None:
    principal = UnifiedPrincipal(
        user_id="user-1", email="u@example.com", display_name="User"
    )
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
        response = client.get("/api/knowledge/page/entity-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "entity-1"
    assert payload["title"] == "Entity One"
    assert payload["metadata"]["created_at"] == "2026-02-19T09:00:00Z"
    assert payload["properties"] == {"status": "active", "description": "Entity One"}
    assert payload["links"][0]["page_id"] == "entity-2"
    assert payload["summary"] == "Root"
    assert "entity" not in payload
    assert payload["content_markdown"] == "Root\n\nChild"
    assert service.page_detail_calls == [{"user_id": "user-1", "page_id": "entity-1"}]


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (KnowledgePageNotFoundError("missing"), 404, "knowledge page not found"),
        (KnowledgePageAccessDeniedError("denied"), 403, "knowledge page access denied"),
        (KnowledgePageUnavailableError("down"), 503, "knowledge page unavailable"),
        (KnowledgePageUpstreamError("failed"), 502, "knowledge page upstream failure"),
    ],
)
def test_api_knowledge_page_maps_errors(
    error: Exception, expected_status: int, expected_detail: str
) -> None:
    principal = UnifiedPrincipal(
        user_id="user-1", email="u@example.com", display_name="User"
    )
    service = FakeKnowledgeService()
    service.page_detail_error = error
    container = build_test_container({KnowledgeServiceProtocol: service})

    app = FastAPI()

    @app.middleware("http")
    async def attach_container(request, call_next):
        request.app.state.container = container
        return await call_next(request)

    app.dependency_overrides[get_required_auth_context] = lambda: principal
    app.include_router(knowledge_router.router, prefix="/api")

    with TestClient(app) as client:
        response = client.get("/api/knowledge/page/entity-1")

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


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


def test_api_knowledge_category_requires_auth() -> None:
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
        response = client.get("/api/knowledge/category")

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication required"}
    assert service.category_calls == []


def test_api_knowledge_category_pages_requires_auth() -> None:
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
        response = client.get("/api/knowledge/category/type-1/pages")

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication required"}
    assert service.category_pages_calls == []


def test_api_knowledge_page_requires_auth() -> None:
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
        response = client.get("/api/knowledge/page/entity-1")

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication required"}
    assert service.page_detail_calls == []
