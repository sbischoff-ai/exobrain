from __future__ import annotations

from typing import Any

import pytest

from app.agents.tools import build_mcp_tools
from app.agents.tools.mcp_tooling import mcp_access_token_context


class _StubMCPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None, str | None]] = []

    async def list_tools(self, *, access_token: str | None = None) -> list[dict[str, Any]]:  # noqa: ARG002
        return [
            {
                "name": "web_search",
                "description": "Search web via MCP",
                "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}},
                    "required": ["query"],
                },
            }
        ]

    async def invoke_tool(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        access_token: str | None = None,
    ) -> Any:
        self.calls.append((tool_name, arguments, access_token))
        return [{"url": "https://example.com"}]

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_build_mcp_tools_maps_to_langchain_tool_flow() -> None:
    client = _StubMCPClient()

    tools = await build_mcp_tools(mcp_client=client)

    assert [tool.name for tool in tools] == ["web_search"]
    result = await tools[0].ainvoke({"query": "langgraph", "max_results": 2})

    assert result == [{"url": "https://example.com"}]
    assert client.calls == [("web_search", {"query": "langgraph", "max_results": 2}, None)]


@pytest.mark.asyncio
async def test_build_mcp_tools_requires_canonical_input_schema_field() -> None:
    class _LegacySchemaMCPClient(_StubMCPClient):
        async def list_tools(self, *, access_token: str | None = None) -> list[dict[str, Any]]:  # noqa: ARG002
            return [
                {
                    "name": "web_search",
                    "description": "Search web via MCP",
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                }
            ]

    tools = await build_mcp_tools(mcp_client=_LegacySchemaMCPClient())

    schema = tools[0].args_schema.model_json_schema()
    assert schema.get("properties") == {}


@pytest.mark.asyncio
async def test_build_mcp_tools_uses_schema_defaults_for_optional_args() -> None:
    class _DefaultSchemaMCPClient(_StubMCPClient):
        async def list_tools(self, *, access_token: str | None = None) -> list[dict[str, Any]]:  # noqa: ARG002
            return [
                {
                    "name": "web_search",
                    "description": "Search web via MCP",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "max_results": {"type": "integer", "default": 5},
                        },
                        "required": ["query"],
                    },
                }
            ]

    client = _DefaultSchemaMCPClient()
    tools = await build_mcp_tools(mcp_client=client)

    await tools[0].ainvoke({"query": "langgraph"})

    assert client.calls == [("web_search", {"query": "langgraph", "max_results": 5}, None)]


@pytest.mark.asyncio
async def test_build_mcp_tools_uses_stream_scoped_access_token() -> None:
    client = _StubMCPClient()
    tools = await build_mcp_tools(mcp_client=client)

    with mcp_access_token_context("token-a"):
        await tools[0].ainvoke({"query": "a", "max_results": 1})
    with mcp_access_token_context("token-b"):
        await tools[0].ainvoke({"query": "b", "max_results": 1})

    assert client.calls == [
        ("web_search", {"query": "a", "max_results": 1}, "token-a"),
        ("web_search", {"query": "b", "max_results": 1}, "token-b"),
    ]
