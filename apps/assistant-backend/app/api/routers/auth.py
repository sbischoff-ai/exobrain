import logging

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.schemas.auth import LoginRequest, SessionResponse, TokenPairResponse, TokenRefreshRequest
from app.core.settings import Settings
from app.dependency_injection import get_container
from app.services.contracts import AuthServiceProtocol

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenPairResponse | SessionResponse,
    summary="Authenticate user and issue session or token credentials",
    description=(
        "Validates user credentials and issues either a browser session cookie or an API token pair "
        "depending on request mode and issuance policy."
    ),
)
async def login(payload: LoginRequest, request: Request, response: Response) -> TokenPairResponse | SessionResponse:
    container = get_container(request)
    auth_service = container.resolve(AuthServiceProtocol)
    settings = container.resolve(Settings)
    principal = await auth_service.login(payload)

    if principal is None:
        logger.info("login request rejected")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    issue_session = payload.session_mode == "web" and payload.issuance_policy == "session"

    if issue_session:
        # Browser mode: persist state in cookie + Redis-backed session store.
        session_id = await auth_service.issue_session(principal)
        response.set_cookie(
            key=settings.auth_cookie_name,
            value=session_id,
            max_age=settings.auth_refresh_token_ttl_seconds,
            httponly=True,
            samesite="lax",
            secure=False,
        )
        logger.debug("issued cookie-backed session", extra={"user_id": principal.user_id})
        return SessionResponse(session_established=True, user_name=principal.display_name)

    # API mode: return access+refresh tokens so stateless clients can authenticate.
    access_token = auth_service.issue_access_token(principal)
    refresh_token = await auth_service.issue_refresh_token(principal)
    logger.debug("issued access and refresh tokens", extra={"user_id": principal.user_id})
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.auth_access_token_ttl_seconds,
    )


@router.post(
    "/token_refresh",
    response_model=TokenPairResponse,
    summary="Rotate refresh token and issue a new token pair",
    description="Consumes a valid refresh token, revokes it, then issues a fresh access+refresh pair.",
)
async def token_refresh(payload: TokenRefreshRequest, request: Request) -> TokenPairResponse:
    container = get_container(request)
    auth_service = container.resolve(AuthServiceProtocol)
    settings = container.resolve(Settings)
    principal = await auth_service.principal_from_refresh_token(payload.refresh_token)
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token")

    await auth_service.revoke_refresh_token(payload.refresh_token)
    access_token = auth_service.issue_access_token(principal)
    refresh_token = await auth_service.issue_refresh_token(principal)
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.auth_access_token_ttl_seconds,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke cookie-backed session",
    description="Clears the auth session cookie and revokes matching Redis-backed session state.",
)
async def logout(request: Request, response: Response) -> None:
    container = get_container(request)
    auth_service = container.resolve(AuthServiceProtocol)
    settings = container.resolve(Settings)
    session_cookie_name = settings.auth_cookie_name
    session_id = request.cookies.get(session_cookie_name)

    await auth_service.revoke_session(session_id)
    response.delete_cookie(key=session_cookie_name, httponly=True, samesite="lax", secure=False)
    logger.info("logout complete")
