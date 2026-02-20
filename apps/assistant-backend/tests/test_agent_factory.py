from __future__ import annotations

import pytest

from app.agents.factory import _load_mock_messages


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
