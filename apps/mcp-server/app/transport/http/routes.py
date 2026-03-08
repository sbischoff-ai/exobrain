from __future__ import annotations

from fastapi import APIRouter

from app.contracts import HealthResponse, ListToolsResponse, ToolInvocation, ToolResult
from app.services.tool_service import ToolService


def build_router(tool_service: ToolService) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse(status="ok")

    @router.get("/mcp/tools", response_model=ListToolsResponse)
    async def list_tools() -> ListToolsResponse:
        return tool_service.list_tools()

    @router.post("/mcp/tools/invoke", response_model=ToolResult)
    async def invoke_tool(invocation: ToolInvocation) -> ToolResult:
        return tool_service.invoke_tool(invocation)

    return router
