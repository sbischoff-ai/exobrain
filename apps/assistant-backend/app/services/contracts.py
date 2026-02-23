from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from typing import Protocol

import asyncpg

from app.api.schemas.auth import LoginRequest, UnifiedPrincipal, UserResponse
from app.services.chat_stream import ChatStreamEvent


class DatabaseServiceProtocol(Protocol):
    """Abstraction for async SQL execution against the assistant Postgres store."""

    async def connect(self) -> None:
        """Initialize underlying DB resources before request handling begins."""

    async def disconnect(self) -> None:
        """Release open DB resources during application shutdown."""

    async def fetchrow(self, query: str, *args: object) -> asyncpg.Record | None:
        """Execute a query and return a single row, or ``None`` when no row matches."""

    async def fetch(self, query: str, *args: object) -> Sequence[asyncpg.Record]:
        """Execute a query and return all matching rows."""

    async def execute(self, query: str, *args: object) -> str:
        """Execute a write statement and return the backend status string."""


class UserServiceProtocol(Protocol):
    """Identity-read contract used by authentication and profile endpoints."""

    async def get_user_by_email(self, email: str) -> dict[str, str] | None:
        """Look up login identity details by email for credential validation flows."""

    async def get_user(self, user_id: str) -> UserResponse | None:
        """Load a user profile by id for authenticated request contexts."""


class ConversationServiceProtocol(Protocol):
    """Persistence contract for conversation and message records."""

    async def ensure_conversation(self, user_id: str, reference: str) -> str:
        """Create or refresh a conversation scoped to ``user_id`` and ``reference``."""

    async def insert_message(
        self,
        *,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        client_message_id: str | None = None,
    ) -> str:
        """Insert or idempotently upsert a message and return its persistent id."""

    async def list_conversations(self, user_id: str, limit: int, before: str | None = None) -> Sequence[asyncpg.Record]:
        """Return paginated conversation summaries ordered newest-first by reference."""

    async def get_conversation_by_reference(self, user_id: str, reference: str) -> asyncpg.Record | None:
        """Load exactly one conversation summary by reference for a user."""

    async def list_messages(
        self,
        user_id: str,
        conversation_reference: str,
        limit: int,
        before_sequence: int | None = None,
    ) -> Sequence[asyncpg.Record]:
        """Return paginated message rows for a single conversation reference."""

    async def search_conversations(self, user_id: str, query: str, limit: int) -> Sequence[asyncpg.Record]:
        """Search conversations by textual query with a caller-supplied limit."""


class JournalServiceProtocol(Protocol):
    """Journal-focused façade over conversation persistence operations."""

    async def ensure_journal(self, user_id: str, journal_reference: str) -> str:
        """Ensure a journal conversation exists and return its conversation id."""

    async def create_journal_message(
        self,
        *,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        client_message_id: str | None = None,
    ) -> str:
        """Persist a journal message tied to an existing conversation id."""

    async def list_journals(self, user_id: str, limit: int, before: str | None = None) -> Sequence[asyncpg.Record]:
        """List journal entries for a user with optional reference cursor pagination."""

    async def get_journal(self, user_id: str, journal_reference: str) -> asyncpg.Record | None:
        """Fetch one journal entry by slash-formatted reference."""

    async def get_today_journal(self, user_id: str, create: bool = False) -> asyncpg.Record | None:
        """Return today's journal entry, creating it first when ``create`` is true."""

    async def list_messages(
        self,
        *,
        user_id: str,
        journal_reference: str,
        limit: int,
        before_sequence: int | None = None,
    ) -> Sequence[asyncpg.Record]:
        """List messages for a journal reference using optional sequence cursor pagination."""

    async def list_today_messages(
        self,
        *,
        user_id: str,
        limit: int,
        before_sequence: int | None = None,
    ) -> Sequence[asyncpg.Record]:
        """List messages for the current-day journal reference."""

    async def search_journals(self, *, user_id: str, query: str, limit: int) -> Sequence[asyncpg.Record]:
        """Search journals by text against reference and message content."""

    def today_reference(self) -> str:
        """Return the canonical UTC ``YYYY/MM/DD`` journal reference string."""


class AuthServiceProtocol(Protocol):
    """Authentication orchestration contract for login, session, and token flows."""

    async def login(self, payload: LoginRequest) -> UnifiedPrincipal | None:
        """Validate credentials and return principal details on success."""

    def issue_access_token(self, principal: UnifiedPrincipal) -> str:
        """Issue a signed short-lived access token for the given principal."""

    async def issue_refresh_token(self, principal: UnifiedPrincipal) -> str:
        """Persist and return a new refresh token for token-based clients."""

    async def principal_from_refresh_token(self, refresh_token: str | None) -> UnifiedPrincipal | None:
        """Resolve a principal from refresh-token state, or ``None`` if invalid."""

    async def revoke_refresh_token(self, refresh_token: str | None) -> None:
        """Invalidate a refresh token so it can no longer be used."""

    async def issue_session(self, principal: UnifiedPrincipal) -> str:
        """Create and persist a browser-session id for the principal."""

    async def revoke_session(self, session_id: str | None) -> None:
        """Invalidate a browser-session id when users log out."""

    async def principal_from_session(self, session_id: str | None) -> UnifiedPrincipal | None:
        """Resolve a principal from session storage, or ``None`` if missing/expired."""

    def principal_from_bearer(self, bearer_token: str | None) -> UnifiedPrincipal | None:
        """Validate and decode bearer access token into a principal."""


class ChatServiceProtocol(Protocol):
    """High-level chat orchestration contract used by HTTP/SSE endpoints."""

    async def start_journal_stream(
        self,
        *,
        principal: UnifiedPrincipal,
        message: str,
        client_message_id: str,
    ) -> str:
        """Start a new assistant stream and return stream id for SSE consumption."""

    async def stream_events(self, stream_id: str) -> AsyncIterator[ChatStreamEvent]:
        """Yield typed stream events for a previously started stream id."""


class SessionStoreProtocol(Protocol):
    """State-store contract for browser sessions and API refresh tokens."""

    async def ping(self) -> bool:
        """Probe store availability during startup checks."""

    async def create_session(self, session_id: str, user_id: str, ttl_seconds: int) -> None:
        """Persist a new user session with TTL enforcement."""

    async def get_user_id(self, session_id: str) -> str | None:
        """Resolve the user id associated with a stored session id."""

    async def revoke_session(self, session_id: str) -> None:
        """Delete a stored session id."""

    async def store_refresh_token(
        self,
        refresh_token: str,
        user_id: str,
        expires_at: datetime,
        ttl_seconds: int,
    ) -> None:
        """Persist refresh-token metadata for token rotation flows."""

    async def get_refresh_token_user_id(self, refresh_token: str) -> str | None:
        """Resolve owning user id for a refresh token."""

    async def revoke_refresh_token(self, refresh_token: str) -> None:
        """Delete a refresh token from persistent state."""

    async def close(self) -> None:
        """Release underlying network resources during shutdown."""
