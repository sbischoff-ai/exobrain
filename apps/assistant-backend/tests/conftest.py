"""Shared test utilities and fixtures for assistant-backend tests."""

from __future__ import annotations

import pytest


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
        if "WHERE c.user_id = $1::uuid AND c.reference = $2" in query:
            return {"id": "conv-1", "reference": args[1]}
        return None

    async def fetch(self, query: str, *args):
        self.fetch_calls.append((query, args))
        if "FROM messages" in query:
            return [{"id": "msg-1", "role": "user"}]
        return [{"id": "conv-1"}]

    async def execute(self, query: str, *args):
        self.execute_calls.append((query, args))
        return "UPDATE 1"


@pytest.fixture
def fake_database_service() -> FakeDatabaseService:
    return FakeDatabaseService()
