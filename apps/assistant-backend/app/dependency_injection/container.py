from __future__ import annotations

import punq
from fastapi import Request

from app.agents.base import ChatAgent
from app.core.settings import Settings
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.contracts import (
    AuthServiceProtocol,
    ChatServiceProtocol,
    ConversationServiceProtocol,
    DatabaseServiceProtocol,
    JournalCacheProtocol,
    JournalServiceProtocol,
    JobPublisherProtocol,
    KnowledgeServiceProtocol,
    SessionStoreProtocol,
    UserServiceProtocol,
)
from app.services.database_service import DatabaseService
from app.services.journal_cache_store import RedisJournalCacheStore
from app.services.journal_service import JournalService
from app.services.job_orchestrator_client import JobOrchestratorClient
from app.services.knowledge_service import KnowledgeService
from app.services.session_store import RedisSessionStore
from app.services.user_service import UserService


def build_container(settings: Settings) -> punq.Container:
    container = punq.Container()
    container.register(Settings, instance=settings)

    container.register(
        DatabaseServiceProtocol,
        factory=lambda: DatabaseService(
            dsn=settings.assistant_db_dsn,
            reshape_schema_query=settings.reshape_schema_query,
        ),
        scope=punq.Scope.singleton,
    )
    container.register(
        SessionStoreProtocol,
        factory=lambda: RedisSessionStore(
            redis_url=settings.assistant_cache_redis_url,
            key_prefix=settings.assistant_cache_key_prefix,
        ),
        scope=punq.Scope.singleton,
    )
    container.register(
        JournalCacheProtocol,
        factory=lambda: RedisJournalCacheStore(
            redis_url=settings.assistant_cache_redis_url,
            key_prefix=settings.assistant_journal_cache_key_prefix,
            jitter_max_seconds=settings.assistant_journal_cache_jitter_max_seconds,
        ),
        scope=punq.Scope.singleton,
    )
    container.register(
        JobPublisherProtocol,
        factory=lambda: JobOrchestratorClient(
            grpc_target=settings.job_orchestrator_grpc_target,
            connect_timeout_seconds=settings.job_orchestrator_connect_timeout_seconds,
        ),
        scope=punq.Scope.singleton,
    )
    container.register(UserServiceProtocol, factory=UserService, scope=punq.Scope.singleton)
    container.register(AuthServiceProtocol, factory=AuthService, scope=punq.Scope.singleton)
    container.register(ConversationServiceProtocol, factory=ConversationService, scope=punq.Scope.singleton)
    container.register(JournalServiceProtocol, factory=JournalService, scope=punq.Scope.singleton)
    container.register(KnowledgeServiceProtocol, factory=KnowledgeService, scope=punq.Scope.singleton)
    container.register(ChatServiceProtocol, factory=ChatService, scope=punq.Scope.singleton)

    return container


def register_chat_agent(container: punq.Container, agent: ChatAgent) -> None:
    container.register(ChatAgent, instance=agent)


def get_container(request: Request) -> punq.Container:
    return request.app.state.container
