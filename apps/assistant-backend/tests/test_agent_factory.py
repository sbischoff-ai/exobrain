from __future__ import annotations

from typing import Any

import pytest

from app.agents.factory import _build_agent_model, _load_mock_messages, build_main_agent
from app.agents.model_provider_chat_model import ModelProviderChatModel
from app.core.settings import Settings
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_openai import ChatOpenAI


class _FakeMCPClient:
    def __init__(self, tools: list[dict[str, Any]] | None = None) -> None:
        self._tools = tools or []

    async def list_tools(self, *, access_token: str | None = None) -> list[dict[str, Any]]:  # noqa: ARG002
        return self._tools

    async def invoke_tool(self, *, tool_name: str, arguments: dict[str, Any] | None = None, access_token: str | None = None) -> Any:  # noqa: ARG002
        return {"tool": tool_name, "arguments": arguments or {}}

    async def close(self) -> None:
        return None


def test_load_mock_messages_uses_new_delimiter(tmp_path) -> None:
    messages_file = tmp_path / "messages.md"
    messages_file.write_text("one\n\n--- message ---\n\ntwo\n", encoding="utf-8")

    messages = _load_mock_messages(str(messages_file))

    assert messages == ["one", "two"]


def test_load_mock_messages_requires_non_empty_chunks(tmp_path) -> None:
    messages_file = tmp_path / "messages.md"
    messages_file.write_text("\n\n--- message ---\n\n", encoding="utf-8")

    with pytest.raises(ValueError):
        _load_mock_messages(str(messages_file))


def test_build_agent_model_uses_fake_list_model_when_mock_enabled(tmp_path) -> None:
    messages_file = tmp_path / "messages.md"
    messages_file.write_text("one\n\n--- message ---\n\ntwo\n", encoding="utf-8")

    settings = Settings(
        MAIN_AGENT_USE_MOCK=True,
        MAIN_AGENT_MOCK_MESSAGES_FILE=str(messages_file),
    )

    model = _build_agent_model(settings)

    assert isinstance(model, FakeListChatModel)


def test_build_agent_model_uses_model_provider_chat_model_when_mock_disabled() -> None:
    settings = Settings(
        MAIN_AGENT_USE_MOCK=False,
        MAIN_AGENT_MODEL="agent",
        MAIN_AGENT_TEMPERATURE=0.2,
        MODEL_PROVIDER_BASE_URL="http://localhost:8010",
    )

    model = _build_agent_model(settings)

    assert isinstance(model, ModelProviderChatModel)
    assert model.model == "agent"
    assert model.base_url == "http://localhost:8010/v1"


def test_build_agent_model_uses_openai_fallback_when_enabled() -> None:
    settings = Settings(
        MAIN_AGENT_USE_MOCK=False,
        MAIN_AGENT_MODEL="agent",
        MAIN_AGENT_TEMPERATURE=0.2,
        MODEL_PROVIDER_BASE_URL="http://localhost:8010",
        MAIN_AGENT_USE_OPENAI_FALLBACK=True,
    )

    model = _build_agent_model(settings)

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "agent"


def test_build_agent_model_uses_openai_compat_when_contract_mode_legacy() -> None:
    settings = Settings(
        MAIN_AGENT_USE_MOCK=False,
        MAIN_AGENT_MODEL="agent",
        MAIN_AGENT_TEMPERATURE=0.2,
        MODEL_PROVIDER_BASE_URL="http://localhost:8010",
        MAIN_AGENT_MODEL_CONTRACT_MODE="legacy_openai_compatible",
    )

    model = _build_agent_model(settings)

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "agent"


def test_build_agent_model_uses_openai_compat_when_rollout_fallback_enabled() -> None:
    settings = Settings(
        MAIN_AGENT_USE_MOCK=False,
        MAIN_AGENT_MODEL="agent",
        MAIN_AGENT_TEMPERATURE=0.2,
        MODEL_PROVIDER_BASE_URL="http://localhost:8010",
        MAIN_AGENT_MODEL_CONTRACT_MODE="native",
        MAIN_AGENT_USE_OPENAI_FALLBACK=True,
    )

    model = _build_agent_model(settings)

    assert isinstance(model, ChatOpenAI)


@pytest.mark.asyncio
async def test_build_main_agent_passes_mcp_tools_and_web_instructions(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    captured: dict[str, object] = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("app.agents.factory.MainAssistantAgent.create", fake_create)

    settings = Settings(
        MAIN_AGENT_USE_MOCK=False,
        MAIN_AGENT_MODEL="gpt-5.2",
        ASSISTANT_DB_DSN="postgresql://unit-test",
        MAIN_AGENT_SYSTEM_PROMPT="Base prompt",
    )

    await build_main_agent(
        settings,
        mcp_client=_FakeMCPClient(
            tools=[
                {
                    "name": "web_search",
                    "description": "Search the web",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                }
            ]
        ),
    )

    assert "web_search" in str(captured["system_prompt"])
    assert "Never fabricate quotes" in str(captured["system_prompt"])
    assert len(captured["tools"]) == 1


@pytest.mark.asyncio
async def test_build_main_agent_skips_tools_for_mock_mode(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    captured: dict[str, object] = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("app.agents.factory.MainAssistantAgent.create", fake_create)

    settings = Settings(
        MAIN_AGENT_USE_MOCK=True,
        ASSISTANT_DB_DSN="postgresql://unit-test",
    )

    await build_main_agent(settings, mcp_client=_FakeMCPClient())

    assert captured["tools"] is None
