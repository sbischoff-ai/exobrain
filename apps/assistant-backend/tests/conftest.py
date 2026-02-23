"""Shared test utilities and fixtures for assistant-backend tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import punq

from app.core.settings import Settings


class FakeDatabaseService:
    """Shared fake DB service used at the external DB boundary in unit tests."""

    def __init__(self) -> None:
        self.fetchrow_calls: list[tuple[str, tuple]] = []
        self.fetch_calls: list[tuple[str, tuple]] = []
        self.execute_calls: list[tuple[str, tuple]] = []

    async def fetchrow(self, query: str, *args):
        self.fetchrow_calls.append((query, args))
        if "INSERT INTO conversations" in query:
            return {"id": "conv-1"}
        if "INSERT INTO messages" in query:
            return {"id": "msg-1"}
        if "INSERT INTO tool_calls" in query:
            return {"id": "tool-1"}
        if "WHERE c.user_id = $1::uuid AND c.reference = $2" in query:
            return {"id": "conv-1", "reference": args[1]}
        if "WHERE c.id = $1::uuid AND c.user_id = $2::uuid" in query:
            return {"reference": "2026/02/19"}
        return None

    async def fetch(self, query: str, *args):
        self.fetch_calls.append((query, args))
        if "FROM messages" in query:
            return [
                {"id": "msg-2", "role": "assistant", "content": "hi", "sequence": 2, "tool_calls": [{"id": "tool-1", "tool_call_id": "tc-1", "title": "Web search", "description": "Searching the web", "response": "Found 1 candidate source", "error": None}]},
                {"id": "msg-1", "role": "user", "content": "hello", "sequence": 1, "tool_calls": []},
            ]
        return [{"id": "conv-1", "reference": "2026/02/19", "message_count": 2, "status": "open"}]

    async def execute(self, query: str, *args):
        self.execute_calls.append((query, args))
        return "UPDATE 1"


class FakeJournalCache:
    """Simple in-memory cache fake implementing journal cache protocol semantics."""

    def __init__(self) -> None:
        self.values: dict[str, object] = {}
        self.indexes: dict[str, set[str]] = {}

    async def ping(self) -> bool:
        return True

    async def get_json(self, key: str):
        return self.values.get(key)

    async def set_json(self, key: str, payload, ttl_seconds: int) -> None:
        self.values[key] = payload

    async def index_key(self, index_key: str, entry_key: str) -> None:
        self.indexes.setdefault(index_key, set()).add(entry_key)

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)

    async def delete_indexed(self, index_key: str) -> None:
        members = self.indexes.pop(index_key, set())
        for key in members:
            self.values.pop(key, None)

    async def close(self) -> None:
        return None


@pytest.fixture
def fake_database_service() -> FakeDatabaseService:
    return FakeDatabaseService()


@pytest.fixture
def fake_journal_cache() -> FakeJournalCache:
    return FakeJournalCache()


@pytest.fixture
def test_settings() -> Settings:
    return Settings()


def build_test_request(container: punq.Container, *, headers: dict[str, str] | None = None, cookies: dict[str, str] | None = None):
    """Build a request-shaped object using a real punq container in app state."""

    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(container=container)),
        headers=headers or {},
        cookies=cookies or {},
    )


def build_test_container(bindings: dict[object, object]) -> punq.Container:
    """Create a punq container and bind protocol/service keys to test doubles."""

    container = punq.Container()
    for key, value in bindings.items():
        container.register(key, instance=value)
    return container
