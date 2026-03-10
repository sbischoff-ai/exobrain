from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import Field

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.adapters.tool_registry import ToolRegistration, ToolRegistry, build_tool_registry
from app.adapters.web_tools import StaticWebSearchClient, WebFetchAdapter, WebSearchAdapter
from app.contracts import ToolMetadata
from app.contracts.base import StrictModel
from app.services.tool_service import ToolService
from app.transport.http.routes import build_router


class UpperToolInput(StrictModel):
    text: str = Field(min_length=1)


class UpperToolOutput(StrictModel):
    text: str


def _build_test_client_with_upper_tool() -> TestClient:
    web_client = StaticWebSearchClient()
    adapters = ToolAdapterRegistry(
        web_search_adapter=WebSearchAdapter(client=web_client),
        web_fetch_adapter=WebFetchAdapter(client=web_client),
    )

    registry = build_tool_registry(adapters)
    upper_registration = ToolRegistration(
        name="upper",
        metadata_provider=lambda: ToolMetadata(
            name="upper",
            description="Uppercase input text.",
            inputSchema=UpperToolInput.model_json_schema(),
        ),
        invocation_parser=UpperToolInput.model_validate,
        handler=lambda args: UpperToolOutput(text=args.text.upper()),
    )
    custom_registry = ToolRegistry(registrations=[*registry.registrations(), upper_registration])

    app = FastAPI()
    app.include_router(build_router(ToolService(registry=custom_registry)))
    return TestClient(app)


def test_registered_tool_appears_in_tools_endpoint() -> None:
    client = _build_test_client_with_upper_tool()

    response = client.get("/mcp/tools")

    assert response.status_code == 200
    names = [tool["name"] for tool in response.json()["tools"]]
    assert "upper" in names


def test_registered_tool_can_be_invoked_without_service_changes() -> None:
    client = _build_test_client_with_upper_tool()

    response = client.post("/mcp/tools/invoke", json={"name": "upper", "arguments": {"text": "hello"}})

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "name": "upper",
        "result": {"text": "HELLO"},
        "metadata": None,
    }
