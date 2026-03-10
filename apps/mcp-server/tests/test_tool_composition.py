from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import Field

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.adapters.tool_registry import ToolRegistration, ToolRegistry
from app.adapters.web_tools import StaticWebSearchClient, WebFetchAdapter, WebSearchAdapter
from app.contracts import ToolMetadata
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
