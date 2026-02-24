"""Unit tests for journal router response shaping."""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.routers import journal as journal_router


def _message_row(*, tool_calls: object) -> dict:
    return {
        "id": "msg-1",
        "role": "assistant",
        "content": "hello",
        "sequence": 1,
        "created_at": datetime.now(UTC),
        "metadata": None,
        "tool_calls": tool_calls,
    }


def test_messages_from_records_accepts_tool_calls_as_json_string() -> None:
    rows = [
        _message_row(
            tool_calls='[{"id":"tool-1","tool_call_id":"tc-1","title":"Web search","description":"Searching","response":"Found source","error":null}]'
        )
    ]

    payload = journal_router._messages_from_records(rows)

    assert payload[0].tool_calls[0].tool_call_id == "tc-1"
    assert payload[0].tool_calls[0].response == "Found source"


def test_messages_from_records_ignores_non_mapping_tool_calls() -> None:
    rows = [_message_row(tool_calls='["unexpected-string"]')]

    payload = journal_router._messages_from_records(rows)

    assert payload[0].tool_calls == []
