"""Unit tests for Redis journal cache store behavior using mocked Redis client."""

from __future__ import annotations

import pytest

from app.services.journal_cache_store import RedisJournalCacheStore


class FakeRedisClient:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int]] = []
        self.set_members: dict[str, set[str]] = {}
        self.closed = False

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int) -> None:
        self.data[key] = value
        self.set_calls.append((key, value, ex))

    async def sadd(self, key: str, value: str) -> None:
        self.set_members.setdefault(key, set()).add(value)

    async def smembers(self, key: str) -> set[str]:
        return self.set_members.get(key, set())

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            removed += int(self.data.pop(key, None) is not None)
            self.set_members.pop(key, None)
        return removed

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_redis_journal_cache_store_set_get_and_index_invalidation() -> None:
    fake_redis = FakeRedisClient()
    store = RedisJournalCacheStore(
        redis_url="redis://unused:6379/0",
        key_prefix="tests:journal-cache",
        jitter_max_seconds=0,
        redis_client=fake_redis,  # type: ignore[arg-type]
    )

    assert await store.ping()

    await store.set_json("key-a", {"value": 1}, ttl_seconds=30)
    assert ("tests:journal-cache:v1:key-a", '{"value": 1}', 30) in fake_redis.set_calls
    assert await store.get_json("key-a") == {"value": 1}

    await store.index_key("index-a", "key-a")
    await store.delete_indexed("index-a")
    assert await store.get_json("key-a") is None

    await store.close()
    assert fake_redis.closed is True
