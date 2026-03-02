from __future__ import annotations

from app.core.settings import Settings
from app.dependency_injection import build_container
from app.services.job_orchestrator_client import JobOrchestratorClient
from app.services.contracts import (
    AuthServiceProtocol,
    ConversationServiceProtocol,
    DatabaseServiceProtocol,
    JournalCacheProtocol,
    JournalServiceProtocol,
    JobPublisherProtocol,
    KnowledgeServiceProtocol,
    SessionStoreProtocol,
    UserServiceProtocol,
)


def test_container_resolves_singleton_services() -> None:
    container = build_container(Settings())

    assert container.resolve(DatabaseServiceProtocol) is container.resolve(DatabaseServiceProtocol)
    assert container.resolve(SessionStoreProtocol) is container.resolve(SessionStoreProtocol)
    assert container.resolve(JournalCacheProtocol) is container.resolve(JournalCacheProtocol)
    assert container.resolve(UserServiceProtocol) is container.resolve(UserServiceProtocol)
    assert container.resolve(AuthServiceProtocol) is container.resolve(AuthServiceProtocol)
    assert container.resolve(ConversationServiceProtocol) is container.resolve(ConversationServiceProtocol)
    assert container.resolve(JournalServiceProtocol) is container.resolve(JournalServiceProtocol)
    assert container.resolve(JobPublisherProtocol) is container.resolve(JobPublisherProtocol)
    assert container.resolve(KnowledgeServiceProtocol) is container.resolve(KnowledgeServiceProtocol)


def test_container_wires_job_publisher_to_job_orchestrator_client() -> None:
    container = build_container(Settings())

    assert isinstance(container.resolve(JobPublisherProtocol), JobOrchestratorClient)
