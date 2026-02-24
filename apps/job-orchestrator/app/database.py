from __future__ import annotations

import asyncpg


class Database:
    def __init__(self, dsn: str, reshape_schema_query: str = "") -> None:
        self._dsn = dsn
        self._reshape_schema_query = reshape_schema_query
        self._pool: asyncpg.Pool | None = None

    async def _initialize_connection(self, connection: asyncpg.Connection) -> None:
        if self._reshape_schema_query.strip():
            await connection.execute(self._reshape_schema_query)

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self._dsn,
                min_size=1,
                max_size=5,
                init=self._initialize_connection,
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def execute(self, query: str, *args: object) -> str:
        if self._pool is None:
            raise RuntimeError("database pool is not connected")
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetchrow(self, query: str, *args: object):
        if self._pool is None:
            raise RuntimeError("database pool is not connected")
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
