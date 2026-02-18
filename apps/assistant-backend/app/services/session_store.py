from __future__ import annotations

from typing import Protocol

from redis.asyncio import Redis


class SessionStore(Protocol):
    """Protocol for storing and resolving assistant auth sessions."""

    async def create_session(self, session_id: str, user_id: str, ttl_seconds: int) -> None:
        ...

    async def get_user_id(self, session_id: str) -> str | None:
        ...

    async def revoke_session(self, session_id: str) -> None:
        ...

    async def close(self) -> None:
        ...


class RedisSessionStore:
    """Redis-backed session store implementation."""

    def __init__(
        self,
        redis_url: str,
        key_prefix: str = "assistant:sessions",
        redis_client: Redis | None = None,
    ) -> None:
        self._redis = redis_client if redis_client is not None else Redis.from_url(redis_url, decode_responses=True)
        self._key_prefix = key_prefix.strip(":")

    async def ping(self) -> bool:
        return bool(await self._redis.ping())

    async def create_session(self, session_id: str, user_id: str, ttl_seconds: int) -> None:
        key = self._session_key(session_id)
        await self._redis.set(key, user_id, ex=ttl_seconds)

    async def get_user_id(self, session_id: str) -> str | None:
        key = self._session_key(session_id)
        value = await self._redis.get(key)
        return str(value) if value else None

    async def revoke_session(self, session_id: str) -> None:
        key = self._session_key(session_id)
        await self._redis.delete(key)

    async def close(self) -> None:
        await self._redis.aclose()

    def _session_key(self, session_id: str) -> str:
        return f"{self._key_prefix}:{session_id}"
