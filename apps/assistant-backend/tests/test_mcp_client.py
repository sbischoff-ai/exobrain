from __future__ import annotations

import urllib.error
from typing import Any

import pytest

from app.services.mcp_client import MCPClient, MCPClientUnavailableError


@pytest.mark.asyncio
async def test_mcp_client_invokes_tool_successfully(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_post_json(self: MCPClient, payload: dict[str, Any]) -> dict[str, Any]:
        captured.update(payload)
        return {"jsonrpc": "2.0", "id": payload["id"], "result": {"content": "ok"}}

    monkeypatch.setattr(MCPClient, "_post_json", _fake_post_json)

    client = MCPClient(base_url="http://localhost:8001/mcp", request_timeout_seconds=0.1)
    result = await client.invoke_tool(tool_name="web_search", arguments={"query": "hello"})

    assert captured["method"] == "tools/call"
    assert captured["params"] == {"name": "web_search", "arguments": {"query": "hello"}}
    assert result == {"content": "ok"}


@pytest.mark.asyncio
async def test_mcp_client_retries_timeout_and_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def _timeout_post_json(self: MCPClient, payload: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG001
        nonlocal attempts
        attempts += 1
        raise urllib.error.URLError("timeout")

    monkeypatch.setattr(MCPClient, "_post_json", _timeout_post_json)

    client = MCPClient(base_url="http://localhost:8001/mcp", request_timeout_seconds=0.1, max_retries=2)

    with pytest.raises(MCPClientUnavailableError):
        await client.list_tools()

    assert attempts == 3


@pytest.mark.asyncio
async def test_mcp_client_handles_async_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _slow_post_json(self: MCPClient, payload: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG001
        import time

        time.sleep(0.1)
        return {"jsonrpc": "2.0", "id": payload["id"], "result": {"tools": []}}

    monkeypatch.setattr(MCPClient, "_post_json", _slow_post_json)

    client = MCPClient(base_url="http://localhost:8001/mcp", request_timeout_seconds=0.01, max_retries=0)

    with pytest.raises(MCPClientUnavailableError):
        await client.list_tools()
