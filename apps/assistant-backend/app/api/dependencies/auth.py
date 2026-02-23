import logging

from fastapi import HTTPException, Request, status

from app.api.schemas.auth import UnifiedPrincipal
from app.core.settings import Settings
from app.dependency_injection import get_container
from app.services.contracts import AuthServiceProtocol

logger = logging.getLogger(__name__)


async def get_optional_auth_context(request: Request) -> UnifiedPrincipal | None:
    container = get_container(request)
    auth_service = container.resolve(AuthServiceProtocol)

    auth_header = request.headers.get("authorization")
    bearer_token: str | None = None
    if auth_header and auth_header.lower().startswith("bearer "):
        bearer_token = auth_header.split(" ", 1)[1]

    principal = auth_service.principal_from_bearer(bearer_token)
    if principal is not None:
        logger.debug("authenticated via bearer token", extra={"user_id": principal.user_id})
        return principal

    settings = container.resolve(Settings)
    session_id = request.cookies.get(settings.auth_cookie_name)
    principal = await auth_service.principal_from_session(session_id)
    if principal is not None:
        logger.debug("authenticated via session", extra={"user_id": principal.user_id})
    return principal


async def get_required_auth_context(request: Request) -> UnifiedPrincipal:
    principal = await get_optional_auth_context(request)
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    return principal
