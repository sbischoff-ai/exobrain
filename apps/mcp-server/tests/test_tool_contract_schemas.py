import pytest
from pydantic import ValidationError

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.adapters.web_tools import StaticWebSearchClient, WebFetchAdapter, WebSearchAdapter
from app.contracts import EchoToolSuccess, ToolErrorEnvelope, ToolInvocation, WebFetchToolOutput, WebSearchToolOutput
from app.main import create_tool_registry
from app.settings import Settings


def _tool_registry():
    web_client = StaticWebSearchClient()
    adapters = ToolAdapterRegistry(
        web_search_adapter=WebSearchAdapter(client=web_client),
        web_fetch_adapter=WebFetchAdapter(client=web_client),
    )
    settings = Settings.model_validate({"APP_ENV": "test", "WEB_SEARCH_PROVIDER": "static"})
    return create_tool_registry(adapters, settings)


def test_invocation_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ToolInvocation.model_validate(
            {
                "name": "echo",
                "arguments": {"text": "hello"},
                "unexpected": "nope",
            }
        )


def test_invocation_schema_rejects_missing_required_fields() -> None:
    add_tool = _tool_registry().get("add")
    assert add_tool is not None

    with pytest.raises(ValidationError):
        add_tool.parse_arguments({})


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


def test_invocation_schema_rejects_missing_web_fetch_url() -> None:
    web_fetch = _tool_registry().get("web_fetch")
    assert web_fetch is not None

    with pytest.raises(ValidationError):
        web_fetch.parse_arguments({"max_chars": 500})


def test_output_schema_rejects_malformed_web_fetch_payload() -> None:
    with pytest.raises(ValidationError):
        WebFetchToolOutput.model_validate({"url": "https://example.com", "title": "x"})
