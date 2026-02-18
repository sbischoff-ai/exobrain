"""Unit-ish tests for Redis session store implementation using local redis-server."""

from __future__ import annotations

import socket
import subprocess
import time

import pytest

from app.services.session_store import RedisSessionStore


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.mark.asyncio
async def test_redis_session_store_create_get_and_revoke() -> None:
    port = _free_port()
    process = subprocess.Popen(
        [
            "redis-server",
            "--port",
            str(port),
            "--save",
            "",
            "--appendonly",
            "no",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        deadline = time.time() + 5
        while time.time() < deadline:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    break
            finally:
                sock.close()
            time.sleep(0.1)

        store = RedisSessionStore(redis_url=f"redis://127.0.0.1:{port}/0", key_prefix="tests:sessions")
        assert await store.ping()

        await store.create_session("session-a", "user-a", ttl_seconds=30)
        assert await store.get_user_id("session-a") == "user-a"

        await store.revoke_session("session-a")
        assert await store.get_user_id("session-a") is None

        await store.close()
    finally:
        process.terminate()
        process.wait(timeout=5)
