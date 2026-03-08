from __future__ import annotations

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.adapters.web_tools import WebToolError
from app.contracts import (
    AddToolInvocation,
    AddToolSuccess,
    EchoToolInvocation,
    EchoToolSuccess,
    ListToolsResponse,
    ToolError,
    ToolErrorEnvelope,
    ToolResult,
    WebSearchToolInvocation,
    WebSearchToolSuccess,
)


class ToolService:
    def __init__(self, registry: ToolAdapterRegistry):
        self._registry = registry

    def list_tools(self) -> ListToolsResponse:
        return ListToolsResponse(tools=self._registry.list_tools())

    def invoke_tool(self, invocation: EchoToolInvocation | AddToolInvocation | WebSearchToolInvocation) -> ToolResult:
        if invocation.name == "echo":
            return EchoToolSuccess(
                name="echo",
                result=self._registry.invoke_echo(invocation.arguments),
                metadata=invocation.metadata,
            )

        if invocation.name == "add":
            return AddToolSuccess(
                name="add",
                result=self._registry.invoke_add(invocation.arguments),
                metadata=invocation.metadata,
            )

        try:
            return WebSearchToolSuccess(
                name="web_search",
                result=self._registry.invoke_web_search(invocation.arguments),
                metadata=invocation.metadata,
            )
        except WebToolError as exc:
            return ToolErrorEnvelope(
                name="web_search",
                error=ToolError(code="WEB_SEARCH_FAILED", message=str(exc)),
                metadata=invocation.metadata,
            )
