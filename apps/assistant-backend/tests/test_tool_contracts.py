from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.contracts.tools import (
    ToolExecutionError,
    ToolInvocationEnvelope,
    ToolMetadata,
    ToolResultEnvelope,
)


def test_tool_metadata_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ToolMetadata(name="web_search", description="desc", json_schema={}, unknown=True)


def test_tool_invocation_requires_tool_name() -> None:
    with pytest.raises(ValidationError):
        ToolInvocationEnvelope(
            tool_name="",
            args={"query": "test"},
            correlation={"request_id": "req-1"},
        )


def test_tool_result_error_status_requires_error_payload() -> None:
    with pytest.raises(ValidationError):
        ToolResultEnvelope[dict](status="error", result={"unexpected": True})


def test_tool_result_ok_status_rejects_error_payload() -> None:
    with pytest.raises(ValidationError):
        ToolResultEnvelope[dict](
            status="ok",
            result={"ok": True},
            error=ToolExecutionError(code="bad", message="should not be present"),
        )
