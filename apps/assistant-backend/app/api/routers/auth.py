from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.schemas.auth import LoginRequest, SessionResponse, TokenPairResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPairResponse | SessionResponse)
async def login(payload: LoginRequest, request: Request, response: Response) -> TokenPairResponse | SessionResponse:
    auth_service: AuthService = request.app.state.auth_service
    principal = await auth_service.login(payload)

    if principal is None:
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
        return SessionResponse(session_established=True, user_name=principal.display_name)

    access_token = auth_service.issue_access_token(principal)
    refresh_token = auth_service.issue_refresh_token(principal)
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=request.app.state.settings.auth_access_token_ttl_seconds,
    )
