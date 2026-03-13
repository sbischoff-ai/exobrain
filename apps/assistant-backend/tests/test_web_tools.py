from __future__ import annotations

from typing import Any

import pytest

from app.agents.tools import build_mcp_tools


class _StubMCPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None, str | None, str | None]] = []

    async def list_tools(self, *, access_token: str | None = None, session_id: str | None = None) -> list[dict[str, Any]]:  # noqa: ARG002
        return [
            {
                "name": "web_search",
                "description": "Search web via MCP",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "max_results": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "web_fetch",
                "description": "Fetch web page via MCP",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                    },
                    "required": ["url"],
                },
            },
        ]

    async def invoke_tool(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        access_token: str | None = None,
        session_id: str | None = None,
    ) -> Any:
        self.calls.append((tool_name, arguments, access_token, session_id))
        if tool_name == "web_search":
            return {"results": [{"url": "https://example.com"}]}
        return {"url": arguments["url"] if arguments else "", "content_text": "Example"}

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_web_tools_discovered_from_mcp_metadata() -> None:
    client = _StubMCPClient()

    tools = await build_mcp_tools(mcp_client=client)

    assert [tool.name for tool in tools] == ["web_search", "web_fetch"]
    web_search_schema = tools[0].args_schema.model_json_schema()
    assert web_search_schema["required"] == ["query"]


@pytest.mark.asyncio
async def test_web_tools_invoke_through_mcp_client() -> None:
    client = _StubMCPClient()

    tools = await build_mcp_tools(mcp_client=client)
    web_search_tool = next(tool for tool in tools if tool.name == "web_search")
    web_fetch_tool = next(tool for tool in tools if tool.name == "web_fetch")

    search_result = await web_search_tool.ainvoke({"query": "langchain", "max_results": 2})
    fetch_result = await web_fetch_tool.ainvoke({"url": "https://example.com/post"})

    assert search_result == {"results": [{"url": "https://example.com"}]}
    assert fetch_result == {"url": "https://example.com/post", "content_text": "Example"}
    assert client.calls == [
        ("web_search", {"query": "langchain", "max_results": 2}, None, None),
        ("web_fetch", {"url": "https://example.com/post"}, None, None),
    ]
