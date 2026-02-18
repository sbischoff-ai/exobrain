import base64
import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.api.schemas.auth import LoginRequest, UnifiedPrincipal
from app.core.settings import Settings
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


@dataclass
class RefreshTokenRecord:
    token: str
    user_id: str
    expires_at: datetime


@dataclass
class SessionRecord:
    session_id: str
    user_id: str
    expires_at: datetime


class JwtTokenValidator:
    """Default JWT implementation; replaceable for OIDC integrations later."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def issue_access_token(self, principal: UnifiedPrincipal) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": principal.user_id,
            "email": principal.email,
            "name": principal.display_name,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self._settings.auth_access_token_ttl_seconds)).timestamp()),
        }
        return jwt.encode(payload, self._settings.auth_jwt_secret, algorithm=self._settings.auth_jwt_algorithm)

    def decode(self, token: str) -> UnifiedPrincipal:
        payload = jwt.decode(
            token,
            self._settings.auth_jwt_secret,
            algorithms=[self._settings.auth_jwt_algorithm],
        )
        return UnifiedPrincipal(
            user_id=payload["sub"],
            email=payload["email"],
            display_name=payload["name"],
        )


def hash_password(password: str, salt: bytes | None = None) -> str:
    password_salt = salt if salt is not None else secrets.token_bytes(16)
    derived_key = hashlib.scrypt(password.encode("utf-8"), salt=password_salt, n=2**14, r=8, p=1)
    return f"scrypt${base64.urlsafe_b64encode(password_salt).decode()}${base64.urlsafe_b64encode(derived_key).decode()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        _, salt_b64, digest_b64 = encoded_hash.split("$", maxsplit=2)
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        digest = base64.urlsafe_b64decode(digest_b64.encode())
    except ValueError:
        logger.warning("password hash format invalid")
        return False

    candidate = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return hmac.compare_digest(candidate, digest)


class AuthService:
    """Authentication orchestration with in-memory session and refresh stores."""

    def __init__(self, settings: Settings, user_service: UserService) -> None:
        self._settings = settings
        self._user_service = user_service
        self._token_validator = JwtTokenValidator(settings)
        self._refresh_tokens: dict[str, RefreshTokenRecord] = {}
        self._sessions: dict[str, SessionRecord] = {}

    async def login(self, payload: LoginRequest) -> UnifiedPrincipal | None:
        user = await self._user_service.get_user_by_email(payload.email)
        if user is None:
            logger.info("login failed: user not found")
            return None

        if not verify_password(payload.password, user["password_hash"]):
            logger.info("login failed: invalid password")
            return None

        logger.info("login succeeded", extra={"user_id": user["id"]})
        return UnifiedPrincipal(
            user_id=user["id"],
            email=user["email"],
            display_name=user["name"],
        )

    def issue_access_token(self, principal: UnifiedPrincipal) -> str:
        logger.debug("issuing access token", extra={"user_id": principal.user_id})
        return self._token_validator.issue_access_token(principal)

    def issue_refresh_token(self, principal: UnifiedPrincipal) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(seconds=self._settings.auth_refresh_token_ttl_seconds)
        self._refresh_tokens[token] = RefreshTokenRecord(token=token, user_id=principal.user_id, expires_at=expires_at)
        logger.debug("issued refresh token", extra={"user_id": principal.user_id})
        return token

    def issue_session(self, principal: UnifiedPrincipal) -> str:
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(seconds=self._settings.auth_refresh_token_ttl_seconds)
        self._sessions[session_id] = SessionRecord(session_id=session_id, user_id=principal.user_id, expires_at=expires_at)
        logger.info("issued session", extra={"user_id": principal.user_id})
        return session_id

    def revoke_session(self, session_id: str | None) -> None:
        if not session_id:
            return
        self._sessions.pop(session_id, None)
        logger.info("session revoked")

    async def principal_from_session(self, session_id: str | None) -> UnifiedPrincipal | None:
        if not session_id:
            return None
        session = self._sessions.get(session_id)
        if session is None or session.expires_at <= datetime.now(UTC):
            logger.debug("session missing or expired")
            return None
        user = await self._user_service.get_user(session.user_id)
        if user is None:
            logger.warning("session user not found", extra={"user_id": session.user_id})
            return None
        return UnifiedPrincipal(user_id=user.id, email=user.email, display_name=user.name)

    def principal_from_bearer(self, bearer_token: str | None) -> UnifiedPrincipal | None:
        if not bearer_token:
            return None
        try:
            return self._token_validator.decode(bearer_token)
        except jwt.PyJWTError:
            logger.info("bearer token validation failed")
            return None
