from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.adapters.web_tools import StaticWebSearchClient, WebFetchAdapter, WebSearchAdapter
from app.main import app, create_app, create_tool_registry
from app.services.auth_service import AuthService
from app.services.tool_service import ToolService
from app.settings import Settings
from app.transport.http.routes import build_router
from tests.auth_helpers import auth_headers


client = TestClient(app)
client.headers.update(auth_headers())


class _StubKnowledgeInterfaceClient:
    def get_schema(self, *, universe_id: str | None = None) -> dict[str, object]:
        return {"node_types": [{"type": {"id": "node.person", "name": "Person"}}]}

    def get_entity_context(self, *, entity_id: str, user_id: str, max_block_level: int) -> dict[str, object]:
        return {
            "entity": {"id": entity_id, "name": "Ada Lovelace", "type_id": "node.person", "aliases": ["Ada"]},
            "blocks": [{"text": "First programmer."}],
            "neighbors": [
                {
                    "other_entity": {
                        "id": "ent_babbage",
                        "name": "Charles Babbage",
                        "type_id": "node.person",
                        "description": "Inventor",
                        "aliases": ["Babbage"],
                    }
                }
            ],
        }


class _FailingKnowledgeInterfaceClient:
    def get_schema(self, *, universe_id: str | None = None) -> dict[str, object]:
        return {"node_types": []}

    def get_entity_context(self, *, entity_id: str, user_id: str, max_block_level: int) -> dict[str, object]:
        raise RuntimeError("ki unavailable")


def _knowledge_client(client: object, *, raise_server_exceptions: bool = True) -> TestClient:
    app_instance = FastAPI()
    adapters = ToolAdapterRegistry(
        web_search_adapter=WebSearchAdapter(client=StaticWebSearchClient()),
        web_fetch_adapter=WebFetchAdapter(client=StaticWebSearchClient()),
        knowledge_interface_client=client,
        knowledge_interface_user_id="user-123",
    )
    tool_service = ToolService(
        registry=create_tool_registry(
            adapters,
            Settings.model_validate({"APP_ENV": "test", "WEB_SEARCH_PROVIDER": "static"}),
        )
    )
    app_instance.include_router(
        build_router(
            tool_service,
            AuthService(Settings.model_validate({"APP_ENV": "test", "WEB_SEARCH_PROVIDER": "static"})),
        )
    )
    test_client = TestClient(app_instance, raise_server_exceptions=raise_server_exceptions)
    test_client.headers.update(auth_headers())
    return test_client


utility_enabled_client = TestClient(
    create_app(
        Settings.model_validate(
            {
                "APP_ENV": "test",
                "WEB_SEARCH_PROVIDER": "static",
                "ENABLE_UTILITY_TOOLS": True,
            }
        )
    )
)
utility_enabled_client.headers.update(auth_headers())

unauthenticated_client = TestClient(
    create_app(
        Settings.model_validate(
            {
                "APP_ENV": "test",
                "WEB_SEARCH_PROVIDER": "static",
            }
        )
    )
)


def test_healthz() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_mcp_endpoints_require_authentication() -> None:
    response = unauthenticated_client.get("/mcp/tools")

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication required"}


def test_mcp_endpoints_reject_invalid_bearer_token() -> None:
    response = unauthenticated_client.get("/mcp/tools", headers={"Authorization": "Bearer invalid.token.value"})

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid authentication token"}


def test_list_tools() -> None:
    response = client.get("/mcp/tools")

    assert response.status_code == 200
    body = response.json()
    assert "resolve_entities" in [tool["name"] for tool in body["tools"]]
    assert [tool["name"] for tool in body["tools"]] == [
        "resolve_entities",
        "get_entity_context",
        "web_search",
        "web_fetch",
    ]
    web_fetch = next(tool for tool in body["tools"] if tool["name"] == "web_fetch")
    assert web_fetch["inputSchema"]["properties"]["url"]["type"] == "string"


def test_list_tools_includes_agent_facing_input_descriptions() -> None:
    response = client.get("/mcp/tools")

    assert response.status_code == 200
    tools = {tool["name"]: tool for tool in response.json()["tools"]}

    # Tool metadata must be self-descriptive enough for autonomous agent tool selection.
    for tool_name, required_phrase_groups in {
        "web_search": [("search", "sources"), ("web", "external")],
        "web_fetch": [("fetch", "extract"), ("url", "page")],
        "resolve_entities": [("resolve", "matching"), ("entities", "entity")],
        "get_entity_context": [("resolve_entities", "canonical"), ("related", "entity")],
    }.items():
        description = tools[tool_name]["description"]
        assert isinstance(description, str)
        assert len(description.strip()) >= 20
        lowered_description = description.lower()
        for phrase_group in required_phrase_groups:
            assert any(phrase in lowered_description for phrase in phrase_group)

    def assert_field_description_contains(
        properties: dict[str, dict[str, str]], field_name: str, required_phrases: list[str]
    ) -> None:
        description = properties[field_name].get("description", "")
        assert isinstance(description, str)
        assert len(description.strip()) >= 20
        lowered_description = description.lower()
        for phrase in required_phrases:
            assert phrase in lowered_description

    web_search_properties = tools["web_search"]["inputSchema"]["properties"]
    assert_field_description_contains(web_search_properties, "query", ["search", "web"])
    assert_field_description_contains(web_search_properties, "max_results", ["maximum", "results"])
    assert_field_description_contains(web_search_properties, "recency_days", ["days", "recently"])
    assert_field_description_contains(web_search_properties, "include_domains", ["allowlist", "domain"])
    assert_field_description_contains(web_search_properties, "exclude_domains", ["blocklist", "domain"])

    web_fetch_properties = tools["web_fetch"]["inputSchema"]["properties"]
    assert_field_description_contains(web_fetch_properties, "url", ["url", "fetch"])
    assert_field_description_contains(web_fetch_properties, "max_chars", ["maximum", "characters"])

    resolve_entities_schema = tools["resolve_entities"]["inputSchema"]
    assert_field_description_contains(resolve_entities_schema["properties"], "entities", ["entities", "resolve"])

    resolve_entity_item_properties = resolve_entities_schema["$defs"]["ResolveEntitiesInputItem"]["properties"]
    assert_field_description_contains(resolve_entity_item_properties, "name", ["entity", "name"])
    assert_field_description_contains(resolve_entity_item_properties, "type_hint", ["category", "matching"])
    assert_field_description_contains(resolve_entity_item_properties, "description_hint", ["disambiguation", "details"])
    assert_field_description_contains(
        resolve_entity_item_properties,
        "expected_existence",
        ["exist", "new"],
    )


def test_list_tools_omits_resolve_entities_when_knowledge_disabled() -> None:
    disabled_client = TestClient(
        create_app(
            Settings.model_validate(
                {
                    "APP_ENV": "test",
                    "WEB_SEARCH_PROVIDER": "static",
                    "ENABLE_KNOWLEDGE_TOOLS": False,
                }
            )
        )
    )
    disabled_client.headers.update(auth_headers())

    response = disabled_client.get("/mcp/tools")

    assert response.status_code == 200
    assert [tool["name"] for tool in response.json()["tools"]] == ["web_search", "web_fetch"]


def test_list_tools_exposes_only_canonical_input_schema_field() -> None:
    response = client.get("/mcp/tools")

    assert response.status_code == 200
    for tool in response.json()["tools"]:
        assert "inputSchema" in tool
        assert "input_schema" not in tool


def test_invoke_echo_tool() -> None:
    response = utility_enabled_client.post(
        "/mcp/tools/invoke",
        json={"name": "echo", "arguments": {"text": "hello"}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "name": "echo",
        "result": {"text": "hello"},
        "metadata": None,
    }


def test_invoke_add_tool() -> None:
    response = utility_enabled_client.post(
        "/mcp/tools/invoke",
        json={"name": "add", "arguments": {"a": 2, "b": 3}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "name": "add",
        "result": {"sum": 5},
        "metadata": None,
    }


def test_invoke_web_search_tool() -> None:
    response = client.post(
        "/mcp/tools/invoke",
        json={"name": "web_search", "arguments": {"query": "exobrain"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["name"] == "web_search"
    assert len(body["result"]["results"]) == 1


def test_invoke_web_fetch_tool() -> None:
    response = client.post(
        "/mcp/tools/invoke",
        json={"name": "web_fetch", "arguments": {"url": "https://example.com/article", "max_chars": 1200}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["name"] == "web_fetch"
    assert body["result"]["url"] == "https://example.com/article"
    assert body["result"]["content_text"]


def test_invoke_web_fetch_tool_rejects_invalid_payload() -> None:
    response = client.post(
        "/mcp/tools/invoke",
        json={"name": "web_fetch", "arguments": {"url": "", "max_chars": 20}},
    )

    assert response.status_code == 422


def test_invoke_tool_rejects_invalid_arguments() -> None:
    response = utility_enabled_client.post(
        "/mcp/tools/invoke",
        json={"name": "add", "arguments": {"a": 2, "b": "nope"}},
    )

    assert response.status_code == 422


def test_invoke_web_fetch_tool_returns_error_envelope_on_adapter_failure(monkeypatch) -> None:
    def _explode(self, *, url: str):  # noqa: ANN001, ARG001
        raise RuntimeError("network down")

    monkeypatch.setattr(StaticWebSearchClient, "extract", _explode)

    response = client.post(
        "/mcp/tools/invoke",
        json={"name": "web_fetch", "arguments": {"url": "https://example.com", "max_chars": 300}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "name": "web_fetch",
        "error": {"code": "WEB_FETCH_FAILED", "message": "web_fetch failed: network down"},
        "metadata": None,
    }


def test_invoke_resolve_entities_tool_returns_placeholder_envelope_shape() -> None:
    response = client.post(
        "/mcp/tools/invoke",
        json={"name": "resolve_entities", "arguments": {"entities": [{"name": "Acme Corp"}]}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["name"] == "resolve_entities"
    assert body["metadata"] is None
    assert isinstance(body["result"]["results"], list)
    assert len(body["result"]["results"]) == 1
    item = body["result"]["results"][0]
    assert item.keys() == {
        "entity_id",
        "name",
        "aliases",
        "entity_type",
        "description",
        "status",
        "confidence",
        "newly_created",
    }


def test_list_tools_includes_get_entity_context_descriptive_metadata() -> None:
    response = client.get("/mcp/tools")

    assert response.status_code == 200
    tools = {tool["name"]: tool for tool in response.json()["tools"]}
    assert "get_entity_context" in tools
    metadata = tools["get_entity_context"]
    assert "canonical" in metadata["description"].lower()
    assert "related" in metadata["description"].lower()
    assert metadata["inputSchema"]["required"] == ["entity_id"]


def test_invoke_get_entity_context_returns_success_envelope_shape() -> None:
    ki_client = _knowledge_client(_StubKnowledgeInterfaceClient())

    response = ki_client.post(
        "/mcp/tools/invoke",
        json={"name": "get_entity_context", "arguments": {"entity_id": "ent_ada"}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "name": "get_entity_context",
        "result": {
            "context_markdown": "## Ada Lovelace\n- Type: `node.person`\n- Aliases: Ada\n\n### Context\n- First programmer.\n\n### Related\n- @ent_babbage: Charles Babbage",
            "related_entities": [
                {
                    "entity_id": "ent_babbage",
                    "name": "Charles Babbage",
                    "aliases": ["Babbage"],
                    "entity_type": "Person",
                    "description": "Inventor",
                }
            ],
        },
        "metadata": None,
    }


def test_invoke_get_entity_context_returns_500_when_ki_client_errors() -> None:
    ki_client = _knowledge_client(_FailingKnowledgeInterfaceClient(), raise_server_exceptions=False)

    response = ki_client.post(
        "/mcp/tools/invoke",
        json={"name": "get_entity_context", "arguments": {"entity_id": "ent_ada"}},
    )

    assert response.status_code == 500
