import pytest
from pydantic import TypeAdapter, ValidationError

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.adapters.web_tools import StaticWebSearchClient, WebFetchAdapter, WebSearchAdapter
from app.contracts import (
    GenericToolSuccessEnvelope,
    GetEntityContextToolInput,
    GetEntityContextToolOutput,
    ResolveEntitiesToolInput,
    ResolveEntitiesToolOutput,
    ToolErrorEnvelope,
    ToolInvocation,
    ToolSuccessEnvelope,
    WebFetchToolOutput,
    WebSearchToolOutput,
)
from app.main import create_tool_registry
from app.settings import Settings


def _tool_registry():
    web_client = StaticWebSearchClient()
    adapters = ToolAdapterRegistry(
        web_search_adapter=WebSearchAdapter(client=web_client),
        web_fetch_adapter=WebFetchAdapter(client=web_client),
    )
    settings = Settings.model_validate({"APP_ENV": "test", "WEB_SEARCH_PROVIDER": "static", "ENABLE_UTILITY_TOOLS": True})
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
        GenericToolSuccessEnvelope.model_validate(
            {
                "ok": True,
                "name": "echo",
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


def test_resolve_entities_input_requires_non_empty_entities() -> None:
    with pytest.raises(ValidationError):
        ResolveEntitiesToolInput.model_validate({"entities": []})


def test_resolve_entities_input_requires_entity_name_field() -> None:
    with pytest.raises(ValidationError):
        ResolveEntitiesToolInput.model_validate(
            {
                "entities": [
                    {
                        "type_hint": "person",
                        "description_hint": "from sales",
                        "expected_existence": "existing",
                    }
                ]
            }
        )


def test_resolve_entities_input_rejects_invalid_entity_name() -> None:
    with pytest.raises(ValidationError):
        ResolveEntitiesToolInput.model_validate(
            {
                "entities": [
                    {
                        "name": "",
                        "type_hint": "person",
                        "description_hint": "from sales",
                        "expected_existence": "existing",
                    }
                ]
            }
        )


def test_resolve_entities_input_rejects_invalid_expected_existence_flag() -> None:
    with pytest.raises(ValidationError):
        ResolveEntitiesToolInput.model_validate(
            {
                "entities": [
                    {
                        "name": "Alice",
                        "expected_existence": "sometimes",
                    }
                ]
            }
        )


def test_resolve_entities_output_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        ResolveEntitiesToolOutput.model_validate(
            {
                "results": [
                    {
                        "entity_id": "e1",
                        "name": "Alice",
                        "aliases": ["A"],
                        "entity_type": "person",
                        "description": "example",
                        "status": "matched",
                        "confidence": 1.2,
                        "newly_created": False,
                    }
                ]
            }
        )


def test_resolve_entities_output_rejects_negative_confidence() -> None:
    with pytest.raises(ValidationError):
        ResolveEntitiesToolOutput.model_validate(
            {
                "results": [
                    {
                        "entity_id": "e1",
                        "name": "Alice",
                        "aliases": ["A"],
                        "entity_type": "person",
                        "description": "example",
                        "status": "matched",
                        "confidence": -0.1,
                        "newly_created": False,
                    }
                ]
            }
        )


def test_resolve_entities_output_requires_canonical_fields() -> None:
    with pytest.raises(ValidationError):
        ResolveEntitiesToolOutput.model_validate(
            {
                "results": [
                    {
                        "entity_id": "e1",
                        "name": "Alice",
                        "aliases": ["A"],
                        "status": "matched",
                        "confidence": 0.9,
                        "newly_created": False,
                    }
                ]
            }
        )


def test_resolve_entities_success_envelope_validates_result_shape() -> None:
    envelope = GenericToolSuccessEnvelope.model_validate(
        {
            "ok": True,
            "name": "resolve_entities",
            "result": {"results": [{"entity_id": "e1"}]},
        }
    )

    assert envelope.name == "resolve_entities"


def test_tool_success_envelope_types_resolve_entities_result() -> None:
    envelope = TypeAdapter(ToolSuccessEnvelope).validate_python(
        {
            "ok": True,
            "name": "resolve_entities",
            "result": {
                "results": [
                    {
                        "entity_id": "e1",
                        "name": "Alice",
                        "aliases": [],
                        "entity_type": "person",
                        "description": "example",
                        "status": "matched",
                        "confidence": 0.5,
                        "newly_created": False,
                    }
                ]
            },
        }
    )

    assert isinstance(envelope, GenericToolSuccessEnvelope)


def test_get_entity_context_input_requires_non_empty_entity_id() -> None:
    with pytest.raises(ValidationError):
        GetEntityContextToolInput.model_validate({"entity_id": ""})


def test_get_entity_context_input_rejects_out_of_range_depth() -> None:
    with pytest.raises(ValidationError):
        GetEntityContextToolInput.model_validate({"entity_id": "e1", "depth": 33})


def test_get_entity_context_output_accepts_resolve_like_related_entity_shape() -> None:
    payload = GetEntityContextToolOutput.model_validate(
        {
            "context_markdown": "# Entity",
            "related_entities": [
                {
                    "entity_id": "e2",
                    "name": "Alice",
                    "aliases": ["A."],
                    "entity_type": "person",
                    "description": "example",
                }
            ],
        }
    )

    assert payload.related_entities[0].entity_id == "e2"
