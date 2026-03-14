from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from app.services.contracts import MCPClientProtocol

_MCP_ACCESS_TOKEN: ContextVar[str | None] = ContextVar("_MCP_ACCESS_TOKEN", default=None)
_MCP_SESSION_ID: ContextVar[str | None] = ContextVar("_MCP_SESSION_ID", default=None)


def current_mcp_access_token() -> str | None:
    return _MCP_ACCESS_TOKEN.get()


def current_mcp_session_id() -> str | None:
    return _MCP_SESSION_ID.get()


@contextmanager
def mcp_auth_context(*, access_token: str | None, session_id: str | None) -> Iterator[None]:
    access_token_token = _MCP_ACCESS_TOKEN.set(access_token)
    session_id_token = _MCP_SESSION_ID.set(session_id)
    try:
        yield
    finally:
        _MCP_SESSION_ID.reset(session_id_token)
        _MCP_ACCESS_TOKEN.reset(access_token_token)


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


def _json_schema_to_annotation(
    *,
    tool_name: str,
    schema: dict[str, Any] | None,
    path: tuple[str, ...],
    root_schema: dict[str, Any],
    seen_refs: set[str] | None = None,
) -> Any:
    if not isinstance(schema, dict):
        return Any

    ref = schema.get("$ref")
    if isinstance(ref, str):
        if seen_refs is None:
            seen_refs = set()
        if ref in seen_refs:
            return Any

        resolved = _resolve_json_schema_ref(root_schema, ref)
        if resolved is not None:
            merged_schema = dict(resolved)
            merged_schema.update({key: value for key, value in schema.items() if key != "$ref"})
            return _json_schema_to_annotation(
                tool_name=tool_name,
                schema=merged_schema,
                path=path,
                root_schema=root_schema,
                seen_refs={*seen_refs, ref},
            )

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and enum_values:
        annotation: Any = Literal.__getitem__(tuple(enum_values))
    else:
        raw_type = schema.get("type")
        nullable = False
        type_names: list[str] = []

        if isinstance(raw_type, str):
            type_names = [raw_type]
        elif isinstance(raw_type, list):
            type_names = [type_name for type_name in raw_type if isinstance(type_name, str)]

        if "null" in type_names:
            nullable = True
            type_names = [type_name for type_name in type_names if type_name != "null"]

        if not type_names:
            if "properties" in schema:
                type_names = ["object"]
            elif "items" in schema:
                type_names = ["array"]

        annotations: list[Any] = []
        for type_name in type_names:
            if type_name == "object":
                properties = schema.get("properties")
                required = schema.get("required")
                if isinstance(properties, dict):
                    required_set = set(required) if isinstance(required, list) else set()
                    fields: dict[str, tuple[Any, Any]] = {}
                    for prop_name, prop_schema in properties.items():
                        if not isinstance(prop_schema, dict):
                            continue
                        prop_annotation = _json_schema_to_annotation(
                            tool_name=tool_name,
                            schema=prop_schema,
                            path=path + (prop_name,),
                            root_schema=root_schema,
                            seen_refs=seen_refs,
                        )
                        description = str(prop_schema.get("description") or "")
                        has_default = "default" in prop_schema
                        default = ... if prop_name in required_set else prop_schema.get("default") if has_default else None
                        fields[prop_name] = (prop_annotation, Field(default=default, description=description))

                    model_name = (
                        "".join(part.capitalize() for part in tool_name.replace("-", "_").split("_"))
                        + ""
                        + "".join(part.capitalize() for part in path)
                        + "Model"
                    )
                    annotations.append(create_model(model_name, **fields))
                    continue
                annotations.append(dict[str, Any])
                continue

            if type_name == "array":
                item_annotation = _json_schema_to_annotation(
                    tool_name=tool_name,
                    schema=schema.get("items") if isinstance(schema.get("items"), dict) else None,
                    path=path + ("item",),
                    root_schema=root_schema,
                    seen_refs=seen_refs,
                )
                annotations.append(list[item_annotation])
                continue

            annotations.append(_json_schema_type_to_python(type_name))

        if not annotations:
            annotation = Any
        else:
            annotation = annotations[0]
            for next_annotation in annotations[1:]:
                annotation = annotation | next_annotation

        if nullable:
            annotation = annotation | None

    return annotation


def _resolve_json_schema_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any] | None:
    if not ref.startswith("#/"):
        return None

    current: Any = root_schema
    for segment in ref[2:].split("/"):
        key = segment.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and key in current:
            current = current[key]
            continue
        return None

    return current if isinstance(current, dict) else None


def _build_args_schema(tool_name: str, inputSchema: dict[str, Any]) -> type[BaseModel]:
    properties = inputSchema.get("properties") if isinstance(inputSchema, dict) else None
    required = inputSchema.get("required") if isinstance(inputSchema, dict) else None

    fields: dict[str, tuple[type[Any], Any]] = {}
    if isinstance(properties, dict):
        required_set = set(required) if isinstance(required, list) else set()
        for arg_name, schema in properties.items():
            if not isinstance(schema, dict):
                continue
            arg_type = _json_schema_to_annotation(
                tool_name=tool_name,
                schema=schema,
                path=(arg_name,),
                root_schema=inputSchema,
            )
            description = str(schema.get("description") or "")
            has_default = "default" in schema
            default = ... if arg_name in required_set else schema.get("default") if has_default else None
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
            return await mcp_client.invoke_tool(
                tool_name=_tool_name,
                arguments=kwargs,
                access_token=current_mcp_access_token(),
                session_id=current_mcp_session_id(),
            )

        tools.append(
            StructuredTool.from_function(
                coroutine=_invoke_tool,
                name=tool_name,
                description=tool_description,
                args_schema=args_schema,
            )
        )

    return tools
