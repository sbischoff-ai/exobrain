from __future__ import annotations

import pytest

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
