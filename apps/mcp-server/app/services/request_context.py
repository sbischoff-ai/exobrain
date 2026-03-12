from __future__ import annotations

from contextvars import ContextVar, Token

from app.services.auth_service import AuthenticatedUser

_current_user: ContextVar[AuthenticatedUser | None] = ContextVar("current_user", default=None)


def set_current_user(user: AuthenticatedUser) -> Token[AuthenticatedUser | None]:
    return _current_user.set(user)


def reset_current_user(token: Token[AuthenticatedUser | None]) -> None:
    _current_user.reset(token)


def get_current_user() -> AuthenticatedUser | None:
    return _current_user.get()
