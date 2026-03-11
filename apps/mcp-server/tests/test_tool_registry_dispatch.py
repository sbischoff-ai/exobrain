from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import Field

from app.adapters.tool_registry import ToolRegistration, ToolRegistry
from app.contracts import GenericToolSuccessEnvelope, ToolInvocation, ToolMetadata
from app.contracts.base import StrictModel
from app.services.tool_service import ToolService
from app.transport.http.routes import build_router


class UpperToolInput(StrictModel):
    text: str = Field(min_length=1)


class UpperToolOutput(StrictModel):
    text: str


def _build_test_client_with_upper_tool() -> TestClient:
    registry = ToolRegistry(registrations=[])
    upper_registration = ToolRegistration(
        name="upper",
        category="custom",
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


def test_service_returns_generic_success_envelope_for_built_in_tool() -> None:
    add_registration = ToolRegistration(
        name="add",
        category="utility",
        metadata_provider=lambda: ToolMetadata(
            name="add",
            description="Add numbers.",
            inputSchema={"type": "object"},
        ),
        invocation_parser=lambda payload: payload,
        handler=lambda args: {"sum": args["a"] + args["b"]},
    )
    service = ToolService(registry=ToolRegistry(registrations=[add_registration]))

    result = service.invoke_tool(ToolInvocation(name="add", arguments={"a": 2, "b": 3}))

    assert isinstance(result, GenericToolSuccessEnvelope)
    assert result.model_dump() == {
        "ok": True,
        "name": "add",
        "result": {"sum": 5},
        "metadata": None,
    }
