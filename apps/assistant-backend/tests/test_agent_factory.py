from __future__ import annotations

import pytest

from app.agents.factory import _build_agent_model, _load_mock_messages, build_main_agent
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


def test_build_agent_model_uses_openai_model_when_mock_disabled(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    settings = Settings(MAIN_AGENT_USE_MOCK=False, MAIN_AGENT_MODEL="gpt-5.2", MAIN_AGENT_TEMPERATURE=0.2)

    model = _build_agent_model(settings)

    assert isinstance(model, ChatOpenAI)


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
    assert len(captured["tools"]) == 2


@pytest.mark.asyncio
async def test_build_main_agent_forwards_web_tool_mock_settings(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    captured_create: dict[str, object] = {}
    captured_tools: dict[str, object] = {}

    async def fake_create(**kwargs):
        captured_create.update(kwargs)
        return object()

    fake_tools = [object()]

    def fake_build_web_tools(**kwargs):
        captured_tools.update(kwargs)
        return fake_tools

    monkeypatch.setattr("app.agents.factory.MainAssistantAgent.create", fake_create)
    monkeypatch.setattr("app.agents.factory.build_web_tools", fake_build_web_tools)

    settings = Settings(
        MAIN_AGENT_USE_MOCK=False,
        ASSISTANT_DB_DSN="postgresql://unit-test",
        WEB_TOOLS_USE_MOCK=True,
        WEB_TOOLS_MOCK_DATA_FILE="mock-data/web-tools.mock.json",
    )

    await build_main_agent(settings)

    assert captured_tools == {
        "tavily_api_key": None,
        "use_mock": True,
        "mock_data_file": "mock-data/web-tools.mock.json",
    }
    assert captured_create["tools"] is fake_tools
