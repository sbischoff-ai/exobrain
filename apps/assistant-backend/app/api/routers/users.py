import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies.auth import get_optional_auth_context, get_required_auth_context
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.users import SelfUserResponse, UserConfigsPatchRequest, UserConfigsResponse
from app.dependency_injection import get_container
from app.services.contracts import UserConfigServiceProtocol, UserServiceProtocol
from app.services.user_config_service import InvalidUserConfigValueError, UnknownUserConfigError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=SelfUserResponse)
async def get_me(
    request: Request,
    principal: UnifiedPrincipal | None = Depends(get_optional_auth_context),
) -> SelfUserResponse:
    if principal is None:
        logger.info("users/me unauthorized")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")

    user_service = get_container(request).resolve(UserServiceProtocol)
    user = await user_service.get_user(principal.user_id)
    if user is None:
        logger.warning("users/me principal missing", extra={"user_id": principal.user_id})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    return SelfUserResponse(name=user.name, email=user.email)


@router.get(
    "/me/configs",
    response_model=UserConfigsResponse,
    summary="Get effective user configs",
    description=(
        "Returns all effective assistant config entries for the authenticated user, including type metadata, "
        "choice options, current effective value, default value, and whether the value is falling back to default."
    ),
)
async def get_me_configs(
    request: Request,
    principal: UnifiedPrincipal = Depends(get_required_auth_context),
) -> UserConfigsResponse:
    config_service = get_container(request).resolve(UserConfigServiceProtocol)
    configs = await config_service.get_effective_configs(principal.user_id)
    return UserConfigsResponse(configs=configs)


@router.patch(
    "/me/configs",
    response_model=UserConfigsResponse,
    summary="Update one or more user configs",
    description=(
        "Applies one or more config updates for the authenticated user, validates config type and allowed choice options, "
        "then returns the full effective config set after updates are persisted."
    ),
    responses={400: {"description": "Config key or value is invalid for the requested update"}},
)
async def patch_me_configs(
    payload: UserConfigsPatchRequest,
    request: Request,
    principal: UnifiedPrincipal = Depends(get_required_auth_context),
) -> UserConfigsResponse:
    config_service = get_container(request).resolve(UserConfigServiceProtocol)
    updates = {entry.key: entry.value for entry in payload.updates}
    try:
        configs = await config_service.update_configs(principal.user_id, updates)
    except (UnknownUserConfigError, InvalidUserConfigValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid config update") from exc
    return UserConfigsResponse(configs=configs)
