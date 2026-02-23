from __future__ import annotations

import json
import logging
import random
from typing import Any

from redis.asyncio import Redis

from app.services.contracts import JournalCacheProtocol

logger = logging.getLogger(__name__)


class RedisJournalCacheStore:
    """Redis-backed JSON cache for assistant journal read endpoints."""

    def __init__(
        self,
        redis_url: str,
        key_prefix: str = "assistant:journal-cache",
        jitter_max_seconds: int = 5,
        redis_client: Redis | None = None,
    ) -> None:
        self._redis = redis_client if redis_client is not None else Redis.from_url(redis_url, decode_responses=True)
        self._key_prefix = key_prefix.strip(":")
        self._jitter_max_seconds = max(0, jitter_max_seconds)

    async def ping(self) -> bool:
        return bool(await self._redis.ping())

    async def get_json(self, key: str) -> Any | None:
        value = await self._redis.get(self._full_key(key))
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.warning("journal cache decode failure", extra={"key": key})
            return None

    async def set_json(self, key: str, payload: Any, ttl_seconds: int) -> None:
        ttl_with_jitter = max(1, ttl_seconds + random.randint(0, self._jitter_max_seconds))
        await self._redis.set(self._full_key(key), json.dumps(payload), ex=ttl_with_jitter)

    async def index_key(self, index_key: str, entry_key: str) -> None:
        full_index_key = self._full_key(index_key)
        await self._redis.sadd(full_index_key, self._full_key(entry_key))

    async def delete(self, key: str) -> None:
        await self._redis.delete(self._full_key(key))

    async def delete_indexed(self, index_key: str) -> None:
        full_index_key = self._full_key(index_key)
        members = await self._redis.smembers(full_index_key)
        if members:
            await self._redis.delete(*list(members))
        await self._redis.delete(full_index_key)

    async def close(self) -> None:
        await self._redis.aclose()

    def _full_key(self, key: str) -> str:
        return f"{self._key_prefix}:v1:{key}"


JournalCacheStore = JournalCacheProtocol
