from fastapi import Request

from app.api.schemas.auth import UnifiedPrincipal
from app.services.auth_service import AuthService


async def get_optional_auth_context(request: Request) -> UnifiedPrincipal | None:
    auth_service: AuthService = request.app.state.auth_service

    auth_header = request.headers.get("authorization")
    bearer_token: str | None = None
    if auth_header and auth_header.lower().startswith("bearer "):
        bearer_token = auth_header.split(" ", 1)[1]

    principal = auth_service.principal_from_bearer(bearer_token)
    if principal is not None:
        return principal

    session_id = request.cookies.get(request.app.state.settings.auth_cookie_name)
    return await auth_service.principal_from_session(session_id)
