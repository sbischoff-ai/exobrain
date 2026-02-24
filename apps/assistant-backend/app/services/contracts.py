from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any
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

    async def insert_tool_call(
        self,
        *,
        message_id: str,
        tool_call_id: str,
        title: str,
        description: str,
        response: str | None = None,
        error: str | None = None,
    ) -> str:
        """Insert one tool-call row associated to a persisted assistant message."""

    async def search_conversations(self, user_id: str, query: str, limit: int) -> Sequence[asyncpg.Record]:
        """Search conversations by textual query with a caller-supplied limit."""

    async def get_reference_by_conversation_id(self, conversation_id: str, user_id: str) -> str | None:
        """Resolve journal reference by conversation id scoped to the owning user."""


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


    async def create_journal_tool_call(
        self,
        *,
        conversation_id: str,
        user_id: str,
        message_id: str,
        tool_call_id: str,
        title: str,
        description: str,
        response: str | None = None,
        error: str | None = None,
    ) -> str:
        """Persist one tool-call row associated to a journal assistant message."""

    async def list_journals(self, user_id: str, limit: int, before: str | None = None) -> Sequence[dict[str, Any]]:
        """List journal entries for a user with optional reference cursor pagination."""

    async def get_journal(self, user_id: str, journal_reference: str) -> dict[str, Any] | None:
        """Fetch one journal entry by slash-formatted reference."""

    async def get_today_journal(self, user_id: str, create: bool = False) -> dict[str, Any] | None:
        """Return today's journal entry, creating it first when ``create`` is true."""

    async def list_messages(
        self,
        *,
        user_id: str,
        journal_reference: str,
        limit: int,
        before_sequence: int | None = None,
    ) -> Sequence[dict[str, Any]]:
        """List messages for a journal reference using optional sequence cursor pagination."""

    async def list_today_messages(
        self,
        *,
        user_id: str,
        limit: int,
        before_sequence: int | None = None,
    ) -> Sequence[dict[str, Any]]:
        """List messages for the current-day journal reference."""

    async def search_journals(self, *, user_id: str, query: str, limit: int) -> Sequence[asyncpg.Record]:
        """Search journals by text against reference and message content."""

    def today_reference(self) -> str:
        """Return the canonical UTC ``YYYY/MM/DD`` journal reference string."""


class JournalCacheProtocol(Protocol):
    """Cache contract for journal read models keyed by user, reference, and cursor."""

    async def ping(self) -> bool:
        """Probe cache availability during startup checks."""

    async def get_json(self, key: str) -> Any | None:
        """Return cached JSON payload for ``key`` or ``None`` when missing."""

    async def set_json(self, key: str, payload: Any, ttl_seconds: int) -> None:
        """Store JSON payload under ``key`` with TTL."""

    async def index_key(self, index_key: str, entry_key: str) -> None:
        """Track ``entry_key`` in a Redis set to support targeted invalidation."""

    async def delete(self, key: str) -> None:
        """Delete a single cache key."""

    async def delete_indexed(self, index_key: str) -> None:
        """Delete all keys tracked by ``index_key`` and then remove the index key."""

    async def close(self) -> None:
        """Release underlying network resources during shutdown."""




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


class JobPublisherProtocol(Protocol):
    """Asynchronous job queue publisher contract."""

    async def connect(self) -> None:
        """Initialize queue client resources during app startup."""

    async def close(self) -> None:
        """Release queue client resources during shutdown."""

    async def enqueue_job(self, *, job_type: str, correlation_id: str, payload: dict[str, object]) -> str:
        """Publish a new job request envelope and return the generated job id."""


class KnowledgeServiceProtocol(Protocol):
    """Service contract for knowledge-graph related asynchronous workflows."""

    async def enqueue_update_job(self, *, user_id: str, journal_reference: str) -> str:
        """Queue a knowledge graph update job based on journal messages."""


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
