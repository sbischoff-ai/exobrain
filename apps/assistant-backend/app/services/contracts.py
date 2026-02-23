from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

import asyncpg

from app.api.schemas.auth import LoginRequest, UnifiedPrincipal, UserResponse
from app.services.chat_stream import ChatStreamEvent


class DatabaseServiceProtocol(Protocol):
    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def fetchrow(self, query: str, *args: object) -> asyncpg.Record | None: ...

    async def fetch(self, query: str, *args: object) -> Sequence[asyncpg.Record]: ...

    async def execute(self, query: str, *args: object) -> str: ...


class UserServiceProtocol(Protocol):
    async def get_user_by_email(self, email: str) -> dict[str, str] | None: ...

    async def get_user(self, user_id: str) -> UserResponse | None: ...


class ConversationServiceProtocol(Protocol):
    async def ensure_conversation(self, user_id: str, reference: str) -> str: ...

    async def insert_message(
        self,
        *,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        client_message_id: str | None = None,
    ) -> str: ...

    async def list_conversations(self, user_id: str, limit: int, before: str | None = None) -> Sequence[asyncpg.Record]: ...

    async def get_conversation_by_reference(self, user_id: str, reference: str) -> asyncpg.Record | None: ...

    async def list_messages(
        self,
        user_id: str,
        conversation_reference: str,
        limit: int,
        before_sequence: int | None = None,
    ) -> Sequence[asyncpg.Record]: ...

    async def search_conversations(self, user_id: str, query: str, limit: int) -> Sequence[asyncpg.Record]: ...


class JournalServiceProtocol(Protocol):
    async def ensure_journal(self, user_id: str, journal_reference: str) -> str: ...

    async def create_journal_message(
        self,
        *,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        client_message_id: str | None = None,
    ) -> str: ...

    async def list_journals(self, user_id: str, limit: int, before: str | None = None) -> Sequence[asyncpg.Record]: ...

    async def get_journal(self, user_id: str, journal_reference: str) -> asyncpg.Record | None: ...

    async def get_today_journal(self, user_id: str, create: bool = False) -> asyncpg.Record | None: ...

    async def list_messages(
        self,
        *,
        user_id: str,
        journal_reference: str,
        limit: int,
        before_sequence: int | None = None,
    ) -> Sequence[asyncpg.Record]: ...

    async def list_today_messages(
        self,
        *,
        user_id: str,
        limit: int,
        before_sequence: int | None = None,
    ) -> Sequence[asyncpg.Record]: ...

    async def search_journals(self, *, user_id: str, query: str, limit: int) -> Sequence[asyncpg.Record]: ...

    def today_reference(self) -> str: ...


class AuthServiceProtocol(Protocol):
    async def login(self, payload: LoginRequest) -> UnifiedPrincipal | None: ...

    def issue_access_token(self, principal: UnifiedPrincipal) -> str: ...

    async def issue_refresh_token(self, principal: UnifiedPrincipal) -> str: ...

    async def principal_from_refresh_token(self, refresh_token: str | None) -> UnifiedPrincipal | None: ...

    async def revoke_refresh_token(self, refresh_token: str | None) -> None: ...

    async def issue_session(self, principal: UnifiedPrincipal) -> str: ...

    async def revoke_session(self, session_id: str | None) -> None: ...

    async def principal_from_session(self, session_id: str | None) -> UnifiedPrincipal | None: ...

    def principal_from_bearer(self, bearer_token: str | None) -> UnifiedPrincipal | None: ...


class ChatServiceProtocol(Protocol):
    async def start_journal_stream(
        self,
        *,
        principal: UnifiedPrincipal,
        message: str,
        client_message_id: str,
    ) -> str: ...

    async def stream_events(self, stream_id: str): ...


class SessionStoreProtocol(Protocol):
    async def ping(self) -> bool: ...

    async def create_session(self, session_id: str, user_id: str, ttl_seconds: int) -> None: ...

    async def get_user_id(self, session_id: str) -> str | None: ...

    async def revoke_session(self, session_id: str) -> None: ...

    async def store_refresh_token(
        self,
        refresh_token: str,
        user_id: str,
        expires_at: datetime,
        ttl_seconds: int,
    ) -> None: ...

    async def get_refresh_token_user_id(self, refresh_token: str) -> str | None: ...

    async def revoke_refresh_token(self, refresh_token: str) -> None: ...

    async def close(self) -> None: ...

