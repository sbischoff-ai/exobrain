from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from app.services.contracts import MCPClientProtocol


def _json_schema_type_to_python(type_name: str | None) -> type[Any]:
    if type_name == "string":
        return str
    if type_name == "integer":
        return int
    if type_name == "number":
        return float
    if type_name == "boolean":
        return bool
    if type_name == "array":
        return list[Any]
    if type_name == "object":
        return dict[str, Any]
    return Any


def _build_args_schema(tool_name: str, input_schema: dict[str, Any]) -> type[BaseModel]:
    properties = input_schema.get("properties") if isinstance(input_schema, dict) else None
    required = input_schema.get("required") if isinstance(input_schema, dict) else None

    fields: dict[str, tuple[type[Any], Any]] = {}
    if isinstance(properties, dict):
        required_set = set(required) if isinstance(required, list) else set()
        for arg_name, schema in properties.items():
            if not isinstance(schema, dict):
                continue
            arg_type = _json_schema_type_to_python(schema.get("type") if isinstance(schema.get("type"), str) else None)
            description = str(schema.get("description") or "")
            default = ... if arg_name in required_set else None
            fields[arg_name] = (arg_type, Field(default=default, description=description))

    model_name = "".join(part.capitalize() for part in tool_name.replace("-", "_").split("_")) + "Args"
    return create_model(model_name, **fields)  # type: ignore[call-overload]


async def build_mcp_tools(*, mcp_client: MCPClientProtocol) -> list[StructuredTool]:
    """Build LangChain tools from MCP tool metadata."""

    tools: list[StructuredTool] = []
    for tool in await mcp_client.list_tools():
        tool_name = str(tool.get("name") or "").strip()
        if not tool_name:
            continue
        tool_description = str(tool.get("description") or f"Invoke MCP tool {tool_name}.")
        args_schema = _build_args_schema(tool_name, tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {})

        async def _invoke_tool(*, _tool_name: str = tool_name, **kwargs: Any) -> Any:
            return await mcp_client.invoke_tool(tool_name=_tool_name, arguments=kwargs)

        tools.append(
            StructuredTool.from_function(
                coroutine=_invoke_tool,
                name=tool_name,
                description=tool_description,
                args_schema=args_schema,
            )
        )

    return tools
