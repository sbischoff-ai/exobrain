from __future__ import annotations

import importlib
import sys
import urllib.error
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.services.mcp_client import MCPClient, MCPClientUnavailableError


@pytest.mark.asyncio
async def test_mcp_client_invokes_tool_successfully(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_request_json(self: MCPClient, path: str, method: str, payload: dict[str, Any] | None, access_token: str | None = None) -> dict[str, Any]:
        captured.update({"path": path, "method": method, "payload": payload, "access_token": access_token})
        return {"ok": True, "name": "web_search", "result": {"content": "ok"}, "metadata": None}

    monkeypatch.setattr(MCPClient, "_request_json", _fake_request_json)

    client = MCPClient(base_url="http://localhost:8001", request_timeout_seconds=0.1)
    result = await client.invoke_tool(tool_name="web_search", arguments={"query": "hello"})

    assert captured["path"] == "/mcp/tools/invoke"
    assert captured["method"] == "POST"
    assert captured["payload"] == {"name": "web_search", "arguments": {"query": "hello"}}
    assert result == {"content": "ok"}
    assert captured["access_token"] is None


@pytest.mark.asyncio
async def test_mcp_client_retries_timeout_and_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def _timeout_request_json(
        self: MCPClient,
        path: str,
        method: str,
        payload: dict[str, Any] | None,
        access_token: str | None = None,
    ) -> dict[str, Any]:  # noqa: ARG001
        nonlocal attempts
        attempts += 1
        raise urllib.error.URLError("timeout")

    monkeypatch.setattr(MCPClient, "_request_json", _timeout_request_json)

    client = MCPClient(base_url="http://localhost:8001", request_timeout_seconds=0.1, max_retries=2)

    with pytest.raises(MCPClientUnavailableError):
        await client.list_tools()

    assert attempts == 3


@pytest.mark.asyncio
async def test_mcp_client_handles_async_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _slow_request_json(
        self: MCPClient,
        path: str,
        method: str,
        payload: dict[str, Any] | None,
        access_token: str | None = None,
    ) -> dict[str, Any]:  # noqa: ARG001
        import time

        time.sleep(0.1)
        return {"tools": []}

    monkeypatch.setattr(MCPClient, "_request_json", _slow_request_json)

    client = MCPClient(base_url="http://localhost:8001", request_timeout_seconds=0.01, max_retries=0)

    with pytest.raises(MCPClientUnavailableError):
        await client.list_tools()


@pytest.mark.asyncio
async def test_mcp_client_list_tools_uses_canonical_input_schema_field(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_request_json(
        self: MCPClient,
        path: str,
        method: str,
        payload: dict[str, Any] | None,
        access_token: str | None = None,
    ) -> dict[str, Any]:  # noqa: ARG001
        return {
            "tools": [
                {"name": "good", "description": "ok", "inputSchema": {"type": "object"}},
                {"name": "legacy", "description": "old", "input_schema": {"type": "object"}},
            ]
        }

    monkeypatch.setattr(MCPClient, "_request_json", _fake_request_json)

    client = MCPClient(base_url="http://localhost:8001", request_timeout_seconds=0.1)
    tools = await client.list_tools()

    canonical = next(tool for tool in tools if tool.get("name") == "good")
    legacy = next(tool for tool in tools if tool.get("name") == "legacy")

    assert isinstance(canonical.get("inputSchema"), dict)
    assert "input_schema" not in canonical
    assert "inputSchema" not in legacy
    assert isinstance(legacy.get("input_schema"), dict)



@pytest.mark.asyncio
async def test_mcp_client_adds_authorization_header_when_access_token_present(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_request_json(
        self: MCPClient,
        path: str,
        method: str,
        payload: dict[str, Any] | None,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        captured.update({"path": path, "method": method, "payload": payload, "access_token": access_token})
        return {"tools": []}

    monkeypatch.setattr(MCPClient, "_request_json", _fake_request_json)

    client = MCPClient(base_url="http://localhost:8001", request_timeout_seconds=0.1)
    await client.list_tools(access_token="token-123")

    assert captured["path"] == "/mcp/tools"
    assert captured["method"] == "GET"
    assert captured["payload"] is None
    assert captured["access_token"] == "token-123"


def test_mcp_client_request_json_sets_authorization_header(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_headers: dict[str, str] = {}

    class _FakeResponse:
        status = 200

        def read(self) -> bytes:
            return b'{"tools": []}'

        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    def _fake_urlopen(request, timeout):  # noqa: ANN001,ARG001
        nonlocal captured_headers
        captured_headers = dict(request.headers.items())
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    client = MCPClient(base_url="http://localhost:8001", request_timeout_seconds=0.1)
    result = client._request_json("/mcp/tools", "GET", None, "abc")

    assert result == {"tools": []}
    assert captured_headers["Authorization"] == "Bearer abc"

@pytest.mark.asyncio
async def test_mcp_client_works_against_real_mcp_server_testclient() -> None:
    mcp_server_root = Path(__file__).resolve().parents[2] / "mcp-server"
    saved_modules = {name: module for name, module in sys.modules.items() if name == "app" or name.startswith("app.")}
    for name in list(saved_modules):
        sys.modules.pop(name, None)

    sys.path.insert(0, str(mcp_server_root))
    try:
        mcp_main = importlib.import_module("app.main")
        mcp_settings = mcp_main.Settings.model_validate({"APP_ENV": "test", "WEB_SEARCH_PROVIDER": "static", "ENABLE_UTILITY_TOOLS": True})
        mcp_app = mcp_main.create_app(mcp_settings)
    finally:
        sys.path.pop(0)
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                sys.modules.pop(name, None)
        sys.modules.update(saved_modules)
    client = TestClient(mcp_app)

    mcp_client = MCPClient(base_url="http://testserver", request_timeout_seconds=0.2, max_retries=0)

    def _testclient_request_json(
        self: MCPClient,
        path: str,
        method: str,
        payload: dict[str, Any] | None,
        access_token: str | None = None,
    ) -> dict[str, Any]:  # noqa: ARG001
        response = client.request(method, path, json=payload)
        response.raise_for_status()
        data = response.json()
        assert isinstance(data, dict)
        return data

    mcp_client._request_json = _testclient_request_json.__get__(mcp_client, MCPClient)

    tools = await mcp_client.list_tools()
    tool_names = [tool.get("name") for tool in tools]
    assert "echo" in tool_names
    assert "add" in tool_names
    assert "web_search" in tool_names

    result = await mcp_client.invoke_tool(tool_name="add", arguments={"a": 2, "b": 3})
    assert result == {"sum": 5}
