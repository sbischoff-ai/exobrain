from __future__ import annotations

import base64
import binascii
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from fastapi import HTTPException, Request, status

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
        if not auth_header:
            return None
        if not auth_header.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication token")

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")

        return self._user_from_token(token)

    def require_user(self, request: Request) -> AuthenticatedUser:
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")

        return self._user_from_token(token)

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
