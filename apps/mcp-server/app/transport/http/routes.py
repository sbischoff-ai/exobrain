from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from fastapi import APIRouter, Depends
from fastapi.exceptions import RequestValidationError
from fastapi import Request
from pydantic import ValidationError

from app.contracts import HealthResponse, ListToolsResponse, ToolExecutionContext, ToolInvocation, ToolResult
from app.services.auth_service import AuthService, AuthenticatedUser
from app.services.request_context import reset_current_user, set_current_user
from app.services.tool_service import ToolService


@contextmanager
def with_authenticated_user(user: AuthenticatedUser) -> Generator[None, None, None]:
    token = set_current_user(user)
    try:
        yield
    finally:
        reset_current_user(token)


def build_router(tool_service: ToolService, auth_service: AuthService) -> APIRouter:
    router = APIRouter()

    def require_auth(request: Request) -> AuthenticatedUser:
        return auth_service.require_user(request)

    @router.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse(status="ok")

    @router.get("/mcp/tools", response_model=ListToolsResponse)
    async def list_tools(_user: AuthenticatedUser = Depends(require_auth)) -> ListToolsResponse:
        return tool_service.list_tools()

    @router.post("/mcp/tools/invoke", response_model=ToolResult)
    async def invoke_tool(
        invocation: ToolInvocation,
        user: AuthenticatedUser = Depends(require_auth),
    ) -> ToolResult:
        try:
            with with_authenticated_user(user):
                return tool_service.invoke_tool(
                    invocation,
                    ToolExecutionContext(user_id=user.user_id, name=user.name),
                )
        except ValidationError as exc:
            raise RequestValidationError(exc.errors()) from exc

    return router
