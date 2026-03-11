from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import Field

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.adapters.tool_registry import ToolRegistration, ToolRegistry
from app.adapters.web_tools import StaticWebSearchClient, WebFetchAdapter, WebSearchAdapter
from app.contracts import ResolveEntitiesToolInput, ToolMetadata
from app.contracts.base import StrictModel
from app.main import create_tool_registry
from app.services.tool_service import ToolService
from app.settings import Settings
from app.transport.http.routes import build_router


class ReverseToolInput(StrictModel):
    text: str = Field(min_length=1)


class ReverseToolOutput(StrictModel):
    text: str


def _settings(**overrides: object) -> Settings:
    base = {
        "APP_ENV": "test",
        "WEB_SEARCH_PROVIDER": "static",
        "MCP_SERVER_PORT": 8090,
        "MCP_SERVER_HOST": "0.0.0.0",
    }
    base.update(overrides)
    return Settings.model_validate(base)


def _adapters() -> ToolAdapterRegistry:
    client = StaticWebSearchClient()
    return ToolAdapterRegistry(web_search_adapter=WebSearchAdapter(client=client), web_fetch_adapter=WebFetchAdapter(client=client))


def test_create_tool_registry_loads_enabled_categories() -> None:
    registry = create_tool_registry(_adapters(), _settings(ENABLED_TOOL_CATEGORIES="utility"))

    assert [tool.name for tool in registry.registrations()] == ["echo", "add"]


def test_create_tool_registry_respects_feature_flags() -> None:
    registry = create_tool_registry(
        _adapters(),
        _settings(ENABLED_TOOL_CATEGORIES="utility,web", ENABLE_WEB_TOOLS=False),
    )

    assert [tool.name for tool in registry.registrations()] == ["echo", "add"]


def test_create_tool_registry_ignores_unknown_categories() -> None:
    registry = create_tool_registry(_adapters(), _settings(ENABLED_TOOL_CATEGORIES="utility,unknown,web"))

    assert [tool.name for tool in registry.registrations()] == ["echo", "add", "web_search", "web_fetch"]


def test_create_tool_registry_preserves_category_order_with_empty_categories() -> None:
    registry = create_tool_registry(_adapters(), _settings(ENABLED_TOOL_CATEGORIES="web,knowledge,utility"))

    assert [tool.name for tool in registry.registrations()] == ["web_search", "web_fetch", "echo", "add"]


def test_new_category_tool_works_without_service_branching_changes() -> None:
    reverse_registration = ToolRegistration(
        name="reverse",
        category="text",
        metadata_provider=lambda: ToolMetadata(
            name="reverse",
            description="Reverse text.",
            inputSchema=ReverseToolInput.model_json_schema(),
        ),
        invocation_parser=ReverseToolInput.model_validate,
        handler=lambda args: ReverseToolOutput(text=args.text[::-1]),
    )
    app = FastAPI()
    app.include_router(build_router(ToolService(registry=ToolRegistry(registrations=[reverse_registration]))))
    client = TestClient(app)

    response = client.post("/mcp/tools/invoke", json={"name": "reverse", "arguments": {"text": "hello"}})

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "name": "reverse",
        "result": {"text": "olleh"},
        "metadata": None,
    }


def test_invoke_resolve_entities_returns_deterministic_placeholders() -> None:
    adapters = _adapters()

    result = adapters.invoke_resolve_entities(
        ResolveEntitiesToolInput.model_validate(
            {
                "entities": [
                    {
                        "name": "  Acme   Corp ",
                        "type_hint": " organization ",
                        "description_hint": "Supplier account",
                        "expected_existence": "new",
                    },
                    {
                        "name": "Jane Doe",
                        "expected_existence": "existing",
                    },
                ]
            }
        )
    )

    assert result.model_dump() == {
        "results": [
            {
                "entity_id": "placeholder-entity-001-acme-corp",
                "name": "Acme Corp",
                "aliases": ["  Acme   Corp "],
                "entity_type": "organization",
                "description": "Supplier account",
                "status": "unresolved",
                "confidence": 0.2,
                "newly_created": True,
            },
            {
                "entity_id": "placeholder-entity-002-jane-doe",
                "name": "Jane Doe",
                "aliases": [],
                "entity_type": "unknown",
                "description": "Placeholder resolution result.",
                "status": "unresolved",
                "confidence": 0.2,
                "newly_created": False,
            },
        ]
    }
