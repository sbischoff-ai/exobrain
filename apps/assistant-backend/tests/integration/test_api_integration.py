"""Integration tests for assistant-backend HTTP API.

These tests exercise endpoints against a running backend URL configured in an env file.
They assume the seeded user exists:
- email: test.user@exobrain.local
- password: password123
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

import httpx
import pytest

SEED_EMAIL = "test.user@exobrain.local"
SEED_PASSWORD = "password123"


@dataclass
class IntegrationConfig:
    base_url: str


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


@pytest.fixture(scope="session")
def integration_config() -> IntegrationConfig:
    env_file = Path(
        os.getenv(
            "ASSISTANT_BACKEND_INTEGRATION_ENV_FILE",
            "tests/integration/.env.integration",
        )
    )
    if not env_file.exists():
        pytest.skip(
            f"integration env file not found: {env_file}. "
            "Copy tests/integration/.env.integration.example and set ASSISTANT_BACKEND_BASE_URL."
        )

    values = _parse_env_file(env_file)
    base_url = values.get("ASSISTANT_BACKEND_BASE_URL")
    if not base_url:
        pytest.skip("ASSISTANT_BACKEND_BASE_URL missing in integration env file")

    return IntegrationConfig(base_url=base_url.rstrip("/"))


@pytest.fixture
def client(integration_config: IntegrationConfig) -> httpx.Client:
    with httpx.Client(base_url=integration_config.base_url, timeout=20.0, follow_redirects=True) as c:
        yield c


@pytest.mark.integration
def test_login_rejects_invalid_credentials(client: httpx.Client) -> None:
    response = client.post(
        "/api/auth/login",
        json={
            "email": SEED_EMAIL,
            "password": "wrong-password",
            "session_mode": "web",
            "issuance_policy": "session",
        },
    )
    assert response.status_code == 401


@pytest.mark.integration
def test_login_web_session_and_users_me_logout(client: httpx.Client) -> None:
    login = client.post(
        "/api/auth/login",
        json={
            "email": SEED_EMAIL,
            "password": SEED_PASSWORD,
            "session_mode": "web",
            "issuance_policy": "session",
        },
    )
    assert login.status_code == 200
    payload = login.json()
    assert payload["session_established"] is True
    assert payload["user_name"]

    users_me = client.get("/api/users/me")
    assert users_me.status_code == 200
    me_payload = users_me.json()
    assert me_payload["email"] == SEED_EMAIL
    assert me_payload["name"]

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204

    users_me_after_logout = client.get("/api/users/me")
    assert users_me_after_logout.status_code == 401


@pytest.mark.integration
def test_login_api_tokens_and_users_me_with_bearer(client: httpx.Client) -> None:
    login = client.post(
        "/api/auth/login",
        json={
            "email": SEED_EMAIL,
            "password": SEED_PASSWORD,
            "session_mode": "api",
            "issuance_policy": "tokens",
        },
    )
    assert login.status_code == 200

    tokens = login.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["token_type"] == "bearer"
    assert int(tokens["expires_in"]) > 0

    users_me = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert users_me.status_code == 200
    assert users_me.json()["email"] == SEED_EMAIL


@pytest.mark.integration
def test_users_me_unauthorized_without_auth(client: httpx.Client) -> None:
    response = client.get("/api/users/me")
    assert response.status_code == 401


@pytest.mark.integration
def test_chat_message_all_auth_variants(client: httpx.Client) -> None:
    anonymous_chat = client.post("/api/chat/message", json={"message": "Hello anonymously"})
    assert anonymous_chat.status_code == 200
    assert anonymous_chat.text.strip()

    token_login = client.post(
        "/api/auth/login",
        json={
            "email": SEED_EMAIL,
            "password": SEED_PASSWORD,
            "session_mode": "api",
            "issuance_policy": "tokens",
        },
    )
    token_login.raise_for_status()
    access_token = token_login.json()["access_token"]

    bearer_chat = client.post(
        "/api/chat/message",
        json={"message": "Hello with bearer"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert bearer_chat.status_code == 200
    assert bearer_chat.text.strip()

    session_login = client.post(
        "/api/auth/login",
        json={
            "email": SEED_EMAIL,
            "password": SEED_PASSWORD,
            "session_mode": "web",
            "issuance_policy": "session",
        },
    )
    session_login.raise_for_status()

    cookie_chat = client.post("/api/chat/message", json={"message": "Hello with session"})
    assert cookie_chat.status_code == 200
    assert cookie_chat.text.strip()
