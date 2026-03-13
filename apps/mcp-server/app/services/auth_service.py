from __future__ import annotations

import base64
import binascii
import hmac
import json
from dataclasses import dataclass
from functools import cached_property
from datetime import UTC, datetime
from hashlib import sha256

from fastapi import HTTPException, Request, status
from redis import Redis

from app.settings import Settings


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    name: str


class AuthService:
    def __init__(self, settings: Settings):
        self._settings = settings

    def optional_user(self, request: Request) -> AuthenticatedUser | None:
        auth_header = request.headers.get("authorization")
        if auth_header:
            return self._user_from_authorization(auth_header)
        return self._user_from_session_header(request)

    def require_user(self, request: Request) -> AuthenticatedUser:
        auth_header = request.headers.get("authorization")
        if auth_header:
            return self._user_from_authorization(auth_header)

        user = self._user_from_session_header(request)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
        return user

    def _user_from_authorization(self, auth_header: str) -> AuthenticatedUser:
        if not auth_header.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication token")

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")

        return self._user_from_token(token)

    def _user_from_session_header(self, request: Request) -> AuthenticatedUser | None:
        if not self._settings.auth_session_introspection_enabled:
            return None

        session_header = self._settings.auth_session_header_name.strip().lower()
        if not session_header:
            return None
        session_id = request.headers.get(session_header)
        if not session_id:
            return None

        user_id = self._redis.get(self._session_key(session_id.strip()))
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication token")

        resolved_user_id = str(user_id).strip()
        if not resolved_user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication token")

        return AuthenticatedUser(user_id=resolved_user_id, name=f"User {resolved_user_id}")

    @cached_property
    def _redis(self) -> Redis:
        return Redis.from_url(self._settings.auth_session_redis_url, decode_responses=True)

    def _session_key(self, session_id: str) -> str:
        prefix = self._settings.auth_session_redis_key_prefix.strip(":")
        return f"{prefix}:session:{session_id}"

    def _user_from_token(self, token: str) -> AuthenticatedUser:
        payload = self._decode_jwt_hs256(token)
        user_id = str(payload.get("sub") or payload.get("user_id") or "").strip()
        name = str(payload.get("name") or payload.get("display_name") or payload.get("email") or "").strip()

        if not user_id or not name:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication token")

        return AuthenticatedUser(user_id=user_id, name=name)
    def _decode_jwt_hs256(self, token: str) -> dict[str, object]:
        if self._settings.auth_jwt_algorithm.upper() != "HS256":
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="unsupported auth algorithm")

        try:
            header_segment, payload_segment, signature_segment = token.split(".")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication token") from exc

        signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
        expected_signature = hmac.new(
            self._settings.auth_jwt_secret.encode("utf-8"),
            signing_input,
            digestmod=sha256,
        ).digest()

        token_signature = self._base64url_decode(signature_segment)
        if not hmac.compare_digest(expected_signature, token_signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication token")

        payload_bytes = self._base64url_decode(payload_segment)
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication token") from exc

        if not isinstance(payload, dict):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication token")

        exp = payload.get("exp")
        if exp is not None:
            if not isinstance(exp, (int, float)):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication token")
            if datetime.now(UTC).timestamp() >= float(exp):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication token")

        return payload

    @staticmethod
    def _base64url_decode(segment: str) -> bytes:
        padded = segment + "=" * ((4 - len(segment) % 4) % 4)
        try:
            return base64.urlsafe_b64decode(padded.encode("utf-8"))
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication token") from exc
