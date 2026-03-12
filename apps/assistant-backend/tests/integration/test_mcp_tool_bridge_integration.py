from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agents.tools import build_mcp_tools
from app.services.mcp_client import (
    MCPClient,
    MCPClientError,
    MCPClientInvalidArgumentError,
    MCPClientNotFoundError,
    MCPClientUnavailableError,
)


def _build_mcp_server_test_client() -> TestClient:
    mcp_server_root = Path(__file__).resolve().parents[3] / "mcp-server"
    saved_modules = {name: module for name, module in sys.modules.items() if name == "app" or name.startswith("app.")}

    for name in list(saved_modules):
        sys.modules.pop(name, None)

    sys.path.insert(0, str(mcp_server_root))
    try:
        mcp_main = importlib.import_module("app.main")
        mcp_app = mcp_main.create_app()
    finally:
        sys.path.pop(0)
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                sys.modules.pop(name, None)
        sys.modules.update(saved_modules)

    return TestClient(mcp_app)


@pytest.mark.asyncio
async def test_build_mcp_tools_integrates_with_mcp_server_web_search() -> None:
    test_client = _build_mcp_server_test_client()
    mcp_client = MCPClient(base_url="http://testserver", request_timeout_seconds=0.5, max_retries=0)

    def _testclient_request_json(
        self: MCPClient,
        path: str,
        method: str,
        payload: dict[str, Any] | None,
        access_token: str | None = None,
    ) -> dict[str, Any]:  # noqa: ARG001
        response = test_client.request(method, path, json=payload)
        data = response.json()
        assert isinstance(data, dict)

        if response.status_code == 404:
            raise MCPClientNotFoundError("mcp endpoint not found")
        if response.status_code in {400, 422}:
            raise MCPClientInvalidArgumentError("mcp request arguments are invalid")
        if response.status_code >= 500:
            raise MCPClientUnavailableError("mcp server unavailable")
        if response.status_code >= 300:
            raise MCPClientError(f"unexpected mcp status: {response.status_code}")

        return data

    mcp_client._request_json = _testclient_request_json.__get__(mcp_client, MCPClient)

    listed_tools = await mcp_client.list_tools()
    web_search_metadata = next(tool for tool in listed_tools if tool.get("name") == "web_search")
    assert isinstance(web_search_metadata.get("inputSchema"), dict)

    tools = await build_mcp_tools(mcp_client=mcp_client)
    web_search_tool = next(tool for tool in tools if tool.name == "web_search")

    schema = web_search_tool.args_schema.model_json_schema()
    required = schema.get("required")
    assert isinstance(required, list)
    assert "query" in required

    result = await web_search_tool.ainvoke({"query": "langchain", "max_results": 1})
    assert isinstance(result, dict)
    assert isinstance(result.get("results"), list)
    first_result = result["results"][0]
    assert first_result["url"].startswith("https://")
    assert first_result["title"]
    assert first_result["snippet"]

    with pytest.raises(MCPClientInvalidArgumentError):
        await web_search_tool.ainvoke({"query": "langchain", "max_results": 0})
