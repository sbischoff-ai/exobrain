from __future__ import annotations

from typing import Any

import pytest

from app.agents.tools import build_mcp_tools
from app.agents.tools.mcp_tooling import mcp_auth_context


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
        session_id: str | None = None,
    ) -> Any:
        self.calls.append((tool_name, arguments, access_token, session_id))
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
    assert client.calls == [("web_search", {"query": "langgraph", "max_results": 2}, None, None)]


@pytest.mark.asyncio
async def test_build_mcp_tools_requires_canonical_input_schema_field() -> None:
    class _LegacySchemaMCPClient(_StubMCPClient):
        async def list_tools(self, *, access_token: str | None = None, session_id: str | None = None) -> list[dict[str, Any]]:  # noqa: ARG002
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
        async def list_tools(self, *, access_token: str | None = None, session_id: str | None = None) -> list[dict[str, Any]]:  # noqa: ARG002
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

    assert client.calls == [("web_search", {"query": "langgraph", "max_results": 5}, None, None)]



@pytest.mark.asyncio
async def test_build_mcp_tools_preserves_nested_array_object_schema() -> None:
    class _ResolveEntitiesMCPClient(_StubMCPClient):
        async def list_tools(self, *, access_token: str | None = None, session_id: str | None = None) -> list[dict[str, Any]]:  # noqa: ARG002
            return [
                {
                    "name": "resolve_entities",
                    "description": "Resolve entities via MCP",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "entities": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "type": {"type": "string"},
                                    },
                                    "required": ["name"],
                                },
                            }
                        },
                        "required": ["entities"],
                    },
                }
            ]

    tools = await build_mcp_tools(mcp_client=_ResolveEntitiesMCPClient())

    schema = tools[0].args_schema.model_json_schema()
    entities_schema = schema["properties"]["entities"]

    item_ref = entities_schema["items"]["$ref"].split("/")[-1]
    item_schema = schema["$defs"][item_ref]

    assert entities_schema["type"] == "array"
    assert item_schema["type"] == "object"
    assert "name" in item_schema["properties"]
    assert "name" in item_schema.get("required", [])


@pytest.mark.asyncio
async def test_build_mcp_tools_keeps_nested_required_fields_in_schema() -> None:
    class _NestedRequiredMCPClient(_StubMCPClient):
        async def list_tools(self, *, access_token: str | None = None, session_id: str | None = None) -> list[dict[str, Any]]:  # noqa: ARG002
            return [
                {
                    "name": "upsert_profile",
                    "description": "Upsert profile",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "profile": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "contact": {
                                        "type": "object",
                                        "properties": {
                                            "email": {"type": "string"},
                                            "phone": {"type": "string"},
                                        },
                                        "required": ["email"],
                                    },
                                },
                                "required": ["name", "contact"],
                            }
                        },
                        "required": ["profile"],
                    },
                }
            ]

    tools = await build_mcp_tools(mcp_client=_NestedRequiredMCPClient())

    schema = tools[0].args_schema.model_json_schema()
    profile_ref = schema["properties"]["profile"]["$ref"].split("/")[-1]
    profile_schema = schema["$defs"][profile_ref]
    contact_ref = profile_schema["properties"]["contact"]["$ref"].split("/")[-1]
    contact_schema = schema["$defs"][contact_ref]

    assert "profile" in schema.get("required", [])
    assert "name" in profile_schema.get("required", [])
    assert "contact" in profile_schema.get("required", [])
    assert "email" in contact_schema.get("required", [])



@pytest.mark.asyncio
async def test_build_mcp_tools_resolves_json_schema_refs_in_nested_items() -> None:
    class _RefSchemaMCPClient(_StubMCPClient):
        async def list_tools(self, *, access_token: str | None = None, session_id: str | None = None) -> list[dict[str, Any]]:  # noqa: ARG002
            return [
                {
                    "name": "resolve_entities",
                    "description": "Resolve entities via MCP",
                    "inputSchema": {
                        "type": "object",
                        "$defs": {
                            "ResolveEntity": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type_hint": {"type": "string"},
                                    "description_hint": {"type": "string"},
                                },
                                "required": ["name"],
                            }
                        },
                        "properties": {
                            "entities": {
                                "type": "array",
                                "items": {"$ref": "#/$defs/ResolveEntity"},
                            }
                        },
                        "required": ["entities"],
                    },
                }
            ]

    tools = await build_mcp_tools(mcp_client=_RefSchemaMCPClient())

    schema = tools[0].args_schema.model_json_schema()
    entities_schema = schema["properties"]["entities"]

    item_ref = entities_schema["items"]["$ref"].split("/")[-1]
    item_schema = schema["$defs"][item_ref]

    assert entities_schema["type"] == "array"
    assert item_schema["type"] == "object"
    assert "name" in item_schema["properties"]
    assert "type_hint" in item_schema["properties"]
    assert "description_hint" in item_schema["properties"]
    assert "name" in item_schema.get("required", [])

@pytest.mark.asyncio
async def test_build_mcp_tools_uses_stream_scoped_auth_context() -> None:
    client = _StubMCPClient()
    tools = await build_mcp_tools(mcp_client=client)

    with mcp_auth_context(access_token="token-a", session_id=None):
        await tools[0].ainvoke({"query": "a", "max_results": 1})
    with mcp_auth_context(access_token="token-b", session_id=None):
        await tools[0].ainvoke({"query": "b", "max_results": 1})

    assert client.calls == [
        ("web_search", {"query": "a", "max_results": 1}, "token-a", None),
        ("web_search", {"query": "b", "max_results": 1}, "token-b", None),
    ]


@pytest.mark.asyncio
async def test_build_mcp_tools_uses_session_id_when_no_access_token() -> None:
    client = _StubMCPClient()
    tools = await build_mcp_tools(mcp_client=client)

    with mcp_auth_context(access_token=None, session_id="session-42"):
        await tools[0].ainvoke({"query": "a", "max_results": 1})

    assert client.calls == [("web_search", {"query": "a", "max_results": 1}, None, "session-42")]
