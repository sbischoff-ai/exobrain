"""Unit tests for Redis session store behavior using mocked Redis client."""

from __future__ import annotations

import pytest

from app.services.session_store import RedisSessionStore


class FakeRedisClient:
    """Small async fake matching Redis methods used by RedisSessionStore."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int]] = []
        self.deleted_keys: list[str] = []
        self.closed = False

    async def ping(self) -> bool:
        return True

    async def set(self, key: str, value: str, ex: int) -> None:
        self.data[key] = value
        self.set_calls.append((key, value, ex))

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def delete(self, key: str) -> int:
        self.deleted_keys.append(key)
        return int(self.data.pop(key, None) is not None)

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_redis_session_store_create_get_revoke_and_close() -> None:
    fake_redis = FakeRedisClient()
    store = RedisSessionStore(
        redis_url="redis://unused:6379/0",
        key_prefix="tests:sessions",
        redis_client=fake_redis,  # type: ignore[arg-type]
    )

    assert await store.ping()

    await store.create_session("session-a", "user-a", ttl_seconds=30)
    assert fake_redis.set_calls == [("tests:sessions:session-a", "user-a", 30)]
    assert await store.get_user_id("session-a") == "user-a"

    await store.revoke_session("session-a")
    assert fake_redis.deleted_keys == ["tests:sessions:session-a"]
    assert await store.get_user_id("session-a") is None

    await store.close()
    assert fake_redis.closed is True
