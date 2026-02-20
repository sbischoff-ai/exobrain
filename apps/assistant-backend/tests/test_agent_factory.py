from __future__ import annotations

import pytest

from app.agents.factory import _build_agent_model, _load_mock_messages
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
