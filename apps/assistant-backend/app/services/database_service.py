from collections.abc import Sequence
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class DatabaseService:
    """Thin asyncpg wrapper used by application services."""

    def __init__(self, dsn: str, reshape_schema_query: str | None = None) -> None:
        self._dsn = dsn
        self._reshape_schema_query = reshape_schema_query or ""
        self._pool: asyncpg.Pool | None = None

    async def _initialize_connection(self, connection: asyncpg.Connection) -> None:
        if self._reshape_schema_query.strip():
            logger.debug("applying reshape schema query on fresh connection")
            await connection.execute(self._reshape_schema_query)

    async def connect(self) -> None:
        if self._pool is None:
            logger.info("creating database connection pool")
            self._pool = await asyncpg.create_pool(
                dsn=self._dsn,
                min_size=1,
                max_size=5,
                init=self._initialize_connection,
            )

    async def disconnect(self) -> None:
        if self._pool is not None:
            logger.info("closing database connection pool")
            await self._pool.close()
            self._pool = None

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        if self._pool is None:
            raise RuntimeError("database service is not connected")
        logger.debug("executing fetchrow", extra={"args_count": len(args)})
        async with self._pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def fetch(self, query: str, *args: Any) -> Sequence[asyncpg.Record]:
        if self._pool is None:
            raise RuntimeError("database service is not connected")
        logger.debug("executing fetch", extra={"args_count": len(args)})
        async with self._pool.acquire() as connection:
            return await connection.fetch(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        if self._pool is None:
            raise RuntimeError("database service is not connected")
        logger.debug("executing statement", extra={"args_count": len(args)})
        async with self._pool.acquire() as connection:
            return await connection.execute(query, *args)
