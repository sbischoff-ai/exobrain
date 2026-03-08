import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts import EchoToolSuccess, ToolErrorEnvelope, ToolInvocation, WebSearchToolOutput


INVOCATION_ADAPTER = TypeAdapter(ToolInvocation)


def test_invocation_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        INVOCATION_ADAPTER.validate_python(
            {
                "name": "echo",
                "arguments": {"text": "hello", "extra": "nope"},
            }
        )


def test_invocation_schema_rejects_missing_required_fields() -> None:
    with pytest.raises(ValidationError):
        INVOCATION_ADAPTER.validate_python({"name": "web_search", "arguments": {}})


def test_output_schema_rejects_malformed_web_search_payload() -> None:
    with pytest.raises(ValidationError):
        WebSearchToolOutput.model_validate({"results": [{"title": "t", "snippet": "s"}]})


def test_error_envelope_requires_typed_error() -> None:
    with pytest.raises(ValidationError):
        ToolErrorEnvelope.model_validate(
            {
                "ok": False,
                "name": "web_search",
                "error": {"code": "X"},
            }
        )


def test_success_envelope_rejects_invalid_result_shape() -> None:
    with pytest.raises(ValidationError):
        EchoToolSuccess.model_validate(
            {
                "ok": True,
                "name": "echo",
                "result": {"message": "wrong"},
            }
        )
