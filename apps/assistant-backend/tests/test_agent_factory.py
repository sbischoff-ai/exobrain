from __future__ import annotations

import pytest

from app.agents.factory import (
    MockTavilyWebTools,
    _build_agent_model,
    _build_web_tools_dependency,
    _load_mock_messages,
    build_main_agent,
)
from app.agents.tools.web import TavilyWebTools
from app.core.settings import Settings
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_openai import ChatOpenAI


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


def test_build_agent_model_uses_openai_client_for_model_provider_when_mock_disabled() -> None:
    settings = Settings(
        MAIN_AGENT_USE_MOCK=False,
        MAIN_AGENT_MODEL="agent",
        MAIN_AGENT_TEMPERATURE=0.2,
        MODEL_PROVIDER_BASE_URL="http://localhost:8010/v1",
    )

    model = _build_agent_model(settings)

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "agent"


def test_build_web_tools_dependency_uses_tavily_by_default() -> None:
    dependency = _build_web_tools_dependency(Settings(WEB_TOOLS_USE_MOCK=False))

    assert isinstance(dependency, TavilyWebTools)
    assert not isinstance(dependency, MockTavilyWebTools)


def test_build_web_tools_dependency_uses_mock_variant_when_enabled(tmp_path) -> None:
    payload = tmp_path / "web-tools.json"
    payload.write_text('{"search":{"results":[]},"extract":{"results":[]}}', encoding="utf-8")

    dependency = _build_web_tools_dependency(
        Settings(
            WEB_TOOLS_USE_MOCK=True,
            WEB_TOOLS_MOCK_DATA_FILE=str(payload),
        )
    )

    assert isinstance(dependency, MockTavilyWebTools)


@pytest.mark.asyncio
async def test_build_main_agent_passes_tools_and_web_instructions(monkeypatch, tmp_path) -> None:
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
        TAVILY_API_KEY="tavily-test",
    )

    await build_main_agent(settings)

    assert "web_search" in str(captured["system_prompt"])
    assert "Never fabricate quotes" in str(captured["system_prompt"])
    assert "KaTeX delimiters: $...$" in str(captured["system_prompt"])
    assert "KaTeX delimiters: $$...$$" in str(captured["system_prompt"])
    assert "Never place $$...$$ inside a sentence" in str(captured["system_prompt"])
    assert "blank line before and after" in str(captured["system_prompt"])
    assert "`mermaid` language tag" in str(captured["system_prompt"])
    assert len(captured["tools"]) == 2


@pytest.mark.asyncio
async def test_build_main_agent_uses_mock_web_tools_dependency(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    captured: dict[str, object] = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("app.agents.factory.MainAssistantAgent.create", fake_create)

    settings = Settings(
        MAIN_AGENT_USE_MOCK=False,
        ASSISTANT_DB_DSN="postgresql://unit-test",
        WEB_TOOLS_USE_MOCK=True,
    )

    await build_main_agent(settings)

    assert len(captured["tools"]) == 2
