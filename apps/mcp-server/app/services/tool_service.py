from __future__ import annotations

from app.adapters.tool_registry import ToolRegistry
from app.adapters.web_tools import WebToolError
from app.contracts import (
    AddToolSuccess,
    EchoToolSuccess,
    GenericToolSuccessEnvelope,
    ListToolsResponse,
    ToolError,
    ToolErrorEnvelope,
    ToolInvocation,
    ToolResult,
    WebFetchToolSuccess,
    WebSearchToolSuccess,
)


class ToolService:
    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def list_tools(self) -> ListToolsResponse:
        return ListToolsResponse(tools=self._registry.list_tools())

    def invoke_tool(self, invocation: ToolInvocation) -> ToolResult:
        registration = self._registry.get(invocation.name)
        if registration is None:
            return ToolErrorEnvelope(
                name=invocation.name,
                error=ToolError(code="TOOL_NOT_FOUND", message=f"Unknown tool: {invocation.name}"),
                metadata=invocation.metadata,
            )

        parsed_arguments = registration.parse_arguments(invocation.arguments)
        try:
            result = registration.handler(parsed_arguments)
            return self._build_success(registration.name, result, invocation)
        except WebToolError as exc:
            if registration.error_code is None:
                raise
            return ToolErrorEnvelope(
                name=registration.name,
                error=ToolError(code=registration.error_code, message=str(exc)),
                metadata=invocation.metadata,
            )

    def _build_success(self, tool_name: str, result: object, invocation: ToolInvocation) -> ToolResult:
        if tool_name == "echo":
            return EchoToolSuccess(name="echo", result=result, metadata=invocation.metadata)
        if tool_name == "add":
            return AddToolSuccess(name="add", result=result, metadata=invocation.metadata)
        if tool_name == "web_search":
            return WebSearchToolSuccess(name="web_search", result=result, metadata=invocation.metadata)
        if tool_name == "web_fetch":
            return WebFetchToolSuccess(name="web_fetch", result=result, metadata=invocation.metadata)
        return GenericToolSuccessEnvelope(name=tool_name, result=result, metadata=invocation.metadata)
