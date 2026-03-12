from __future__ import annotations

from app.adapters.tool_registry import ToolRegistry
from app.adapters.web_tools import WebToolError
from app.contracts import (
    GenericToolSuccessEnvelope,
    ListToolsResponse,
    ToolError,
    ToolErrorEnvelope,
    ToolExecutionContext,
    ToolInvocation,
    ToolResult,
)


class ToolService:
    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def list_tools(self) -> ListToolsResponse:
        return ListToolsResponse(tools=self._registry.list_tools())

    def invoke_tool(self, invocation: ToolInvocation, context: ToolExecutionContext) -> ToolResult:
        registration = self._registry.get(invocation.name)
        if registration is None:
            return ToolErrorEnvelope(
                name=invocation.name,
                error=ToolError(code="TOOL_NOT_FOUND", message=f"Unknown tool: {invocation.name}"),
                metadata=invocation.metadata,
            )

        parsed_arguments = registration.parse_arguments(invocation.arguments)
        try:
            result = registration.handler(parsed_arguments, context)
            return GenericToolSuccessEnvelope(name=registration.name, result=result, metadata=invocation.metadata)
        except WebToolError as exc:
            if registration.error_code is None:
                raise
            return ToolErrorEnvelope(
                name=registration.name,
                error=ToolError(code=registration.error_code, message=str(exc)),
                metadata=invocation.metadata,
            )
