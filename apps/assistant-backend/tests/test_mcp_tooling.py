from __future__ import annotations

from typing import Any

import pytest

from app.agents.tools import build_mcp_tools


class _StubMCPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def list_tools(self) -> list[dict[str, Any]]:
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

    async def invoke_tool(self, *, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        self.calls.append((tool_name, arguments))
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
    assert client.calls == [("web_search", {"query": "langgraph", "max_results": 2})]
