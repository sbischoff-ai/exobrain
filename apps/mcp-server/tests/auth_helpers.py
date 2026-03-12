from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta


def build_bearer_token(
    *,
    user_id: str = "user-123",
    name: str = "Test User",
    secret: str = "dev-secret-change-me",
    ttl_seconds: int = 600,
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "name": name,
        "exp": int((datetime.now(UTC) + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    header_segment = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_segment = _base64url_encode(signature)
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def auth_headers(**kwargs: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {build_bearer_token(**kwargs)}"}


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")
