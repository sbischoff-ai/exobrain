from __future__ import annotations

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.contracts import (
    AddToolInvocation,
    AddToolResult,
    EchoToolInvocation,
    EchoToolResult,
    ListToolsResponse,
    ToolResult,
)


class ToolService:
    def __init__(self, registry: ToolAdapterRegistry):
        self._registry = registry

    def list_tools(self) -> ListToolsResponse:
        return ListToolsResponse(tools=self._registry.list_tools())

    def invoke_tool(self, invocation: EchoToolInvocation | AddToolInvocation) -> ToolResult:
        if invocation.name == "echo":
            return EchoToolResult(name="echo", result=self._registry.invoke_echo(invocation.arguments))

        return AddToolResult(name="add", result=self._registry.invoke_add(invocation.arguments))
