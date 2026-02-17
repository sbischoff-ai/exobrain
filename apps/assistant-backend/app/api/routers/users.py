from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies.auth import get_optional_auth_context
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.users import SelfUserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=SelfUserResponse)
async def get_me(
    request: Request,
    principal: UnifiedPrincipal | None = Depends(get_optional_auth_context),
) -> SelfUserResponse:
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")

    user = await request.app.state.user_service.get_user(principal.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    return SelfUserResponse(name=user.name, email=user.email)
