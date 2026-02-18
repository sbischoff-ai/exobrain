import logging

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.schemas.auth import LoginRequest, SessionResponse, TokenPairResponse
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPairResponse | SessionResponse)
async def login(payload: LoginRequest, request: Request, response: Response) -> TokenPairResponse | SessionResponse:
    auth_service: AuthService = request.app.state.auth_service
    principal = await auth_service.login(payload)

    if principal is None:
        logger.info("login request rejected")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    issue_session = payload.session_mode == "web" and payload.issuance_policy == "session"

    if issue_session:
        session_id = auth_service.issue_session(principal)
        response.set_cookie(
            key=request.app.state.settings.auth_cookie_name,
            value=session_id,
            max_age=request.app.state.settings.auth_refresh_token_ttl_seconds,
            httponly=True,
            samesite="lax",
            secure=False,
        )
        logger.debug("issued cookie-backed session", extra={"user_id": principal.user_id})
        return SessionResponse(session_established=True, user_name=principal.display_name)

    access_token = auth_service.issue_access_token(principal)
    refresh_token = auth_service.issue_refresh_token(principal)
    logger.debug("issued access and refresh tokens", extra={"user_id": principal.user_id})
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=request.app.state.settings.auth_access_token_ttl_seconds,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response) -> None:
    auth_service: AuthService = request.app.state.auth_service
    session_cookie_name = request.app.state.settings.auth_cookie_name
    session_id = request.cookies.get(session_cookie_name)

    auth_service.revoke_session(session_id)
    response.delete_cookie(key=session_cookie_name, httponly=True, samesite="lax", secure=False)
    logger.info("logout complete")
