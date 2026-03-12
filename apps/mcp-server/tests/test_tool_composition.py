from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import Field

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.adapters.tool_registry import ToolRegistration, ToolRegistry
from app.adapters.web_tools import StaticWebSearchClient, WebFetchAdapter, WebSearchAdapter
from app.contracts import GetEntityContextToolInput, ResolveEntitiesToolInput, ToolMetadata
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
    registry = create_tool_registry(_adapters(), _settings(ENABLED_TOOL_CATEGORIES="utility", ENABLE_UTILITY_TOOLS=True))

    assert [tool.name for tool in registry.registrations()] == ["echo", "add"]


def test_create_tool_registry_respects_feature_flags() -> None:
    registry = create_tool_registry(
        _adapters(),
        _settings(ENABLED_TOOL_CATEGORIES="utility,web", ENABLE_UTILITY_TOOLS=True, ENABLE_WEB_TOOLS=False),
    )

    assert [tool.name for tool in registry.registrations()] == ["echo", "add"]


def test_create_tool_registry_ignores_unknown_categories() -> None:
    registry = create_tool_registry(_adapters(), _settings(ENABLED_TOOL_CATEGORIES="utility,unknown,web", ENABLE_UTILITY_TOOLS=True))

    assert [tool.name for tool in registry.registrations()] == ["echo", "add", "web_search", "web_fetch"]


def test_create_tool_registry_preserves_category_order_with_empty_categories() -> None:
    registry = create_tool_registry(_adapters(), _settings(ENABLED_TOOL_CATEGORIES="web,knowledge,utility", ENABLE_UTILITY_TOOLS=True))

    assert [tool.name for tool in registry.registrations()] == [
        "web_search",
        "web_fetch",
        "resolve_entities",
        "get_entity_context",
        "echo",
        "add",
    ]


def test_create_tool_registry_includes_knowledge_by_default() -> None:
    registry = create_tool_registry(_adapters(), _settings())

    assert [tool.name for tool in registry.registrations()] == [
        "resolve_entities",
        "get_entity_context",
        "web_search",
        "web_fetch",
    ]


def test_create_tool_registry_includes_knowledge_when_flag_enabled() -> None:
    registry = create_tool_registry(
        _adapters(),
        _settings(ENABLED_TOOL_CATEGORIES="knowledge", ENABLE_KNOWLEDGE_TOOLS=True),
    )

    registrations = registry.registrations()
    assert [tool.name for tool in registrations] == ["resolve_entities", "get_entity_context"]
    assert [tool.category for tool in registrations] == ["knowledge", "knowledge"]


def test_create_tool_registry_excludes_knowledge_when_flag_disabled() -> None:
    registry = create_tool_registry(
        _adapters(),
        _settings(ENABLED_TOOL_CATEGORIES="utility,knowledge", ENABLE_UTILITY_TOOLS=True, ENABLE_KNOWLEDGE_TOOLS=False),
    )

    registrations = registry.registrations()
    assert [tool.name for tool in registrations] == ["echo", "add"]
    assert all(tool.category != "knowledge" for tool in registrations)




def test_create_tool_registry_marks_get_entity_context_as_knowledge() -> None:
    registry = create_tool_registry(
        _adapters(),
        _settings(ENABLED_TOOL_CATEGORIES="knowledge", ENABLE_KNOWLEDGE_TOOLS=True),
    )

    tool_by_name = {tool.name: tool for tool in registry.registrations()}
    assert "get_entity_context" in tool_by_name
    assert tool_by_name["get_entity_context"].category == "knowledge"

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


class _FakeKnowledgeInterfaceClient:
    def __init__(self) -> None:
        self.context_calls: list[dict[str, object]] = []
        self.schema_calls: list[dict[str, object]] = []

    def get_schema(self, *, universe_id: str | None = None) -> dict[str, object]:
        self.schema_calls.append({"universe_id": universe_id})
        return {
            "node_types": [
                {"type": {"id": "node.person", "name": "Person"}},
                {"type": {"id": "node.organization", "name": "Organization"}},
            ]
        }

    def get_entity_context(self, *, entity_id: str, user_id: str, max_block_level: int) -> dict[str, object]:
        self.context_calls.append(
            {
                "entity_id": entity_id,
                "user_id": user_id,
                "max_block_level": max_block_level,
            }
        )
        return {
            "entity": {
                "id": entity_id,
                "name": "Ada Lovelace",
                "type_id": "node.person",
                "aliases": ["Ada"],
            },
            "blocks": [
                {"text": "First programmer."},
                {
                    "text": "Collaborated with Charles Babbage.",
                    "neighbors": [
                        {
                            "edge_type": "COLLABORATED_WITH",
                            "direction": "OUTGOING",
                            "other_entity": {
                                "id": "ent_babbage",
                                "name": "Charles Babbage",
                                "type_id": "node.person",
                                "description": "Inventor and mathematician",
                                "aliases": ["Babbage"],
                            },
                        },
                        {
                            "edge_type": "ASSOCIATED_WITH",
                            "direction": "OUTGOING",
                            "other_entity": {
                                "id": "ent_analytical_engine",
                                "name": "Analytical Engine",
                                "type_id": "node.machine",
                            },
                        },
                    ],
                },
            ],
            "neighbors": [
                {
                    "edge_type": "COLLABORATED_WITH",
                    "direction": "OUTGOING",
                    "other_entity": {
                        "id": "ent_babbage",
                        "name": "Charles Babbage",
                        "type_id": "node.person",
                        "description": "Inventor and mathematician",
                        "aliases": ["Babbage"],
                    },
                }
            ],
        }


def test_invoke_get_entity_context_uses_default_depth_and_maps_output() -> None:
    web_client = StaticWebSearchClient()
    ki_client = _FakeKnowledgeInterfaceClient()
    adapters = ToolAdapterRegistry(
        web_search_adapter=WebSearchAdapter(client=web_client),
        web_fetch_adapter=WebFetchAdapter(client=web_client),
        knowledge_interface_client=ki_client,
        knowledge_interface_user_id="user-123",
    )

    result = adapters.invoke_get_entity_context(GetEntityContextToolInput.model_validate({"entity_id": "ent_ada"}))

    assert [entity.entity_id for entity in result.related_entities] == ["ent_babbage", "ent_analytical_engine"]
    assert ki_client.context_calls == [
        {
            "entity_id": "ent_ada",
            "user_id": "user-123",
            "max_block_level": 3,
        }
    ]
    assert ki_client.schema_calls == [{"universe_id": None}]
    assert result.model_dump() == {
        "context_markdown": "## Ada Lovelace\n- Type: `node.person`\n- Aliases: Ada\n\n### Context\n- First programmer.\n- Collaborated with Charles Babbage.\n\n### Related\n- @ent_analytical_engine: Analytical Engine\n- @ent_babbage: Charles Babbage",
        "related_entities": [
            {
                "entity_id": "ent_babbage",
                "name": "Charles Babbage",
                "aliases": ["Babbage"],
                "entity_type": "Person",
                "description": "Inventor and mathematician",
            },
            {
                "entity_id": "ent_analytical_engine",
                "name": "Analytical Engine",
                "aliases": [],
                "entity_type": "node.machine",
                "description": "Related entity Analytical Engine",
            },
        ],
    }




def test_invoke_get_entity_context_maps_ki_response_deterministically() -> None:
    web_client = StaticWebSearchClient()
    ki_client = _FakeKnowledgeInterfaceClient()
    adapters = ToolAdapterRegistry(
        web_search_adapter=WebSearchAdapter(client=web_client),
        web_fetch_adapter=WebFetchAdapter(client=web_client),
        knowledge_interface_client=ki_client,
        knowledge_interface_user_id="user-123",
    )

    result = adapters.invoke_get_entity_context(
        GetEntityContextToolInput.model_validate({"entity_id": "ent_ada", "depth": 4, "focus": "collaboration"})
    )

    assert ki_client.context_calls[-1] == {
        "entity_id": "ent_ada",
        "user_id": "user-123",
        "max_block_level": 4,
    }
    assert result.context_markdown.startswith("## Ada Lovelace")
    assert result.context_markdown.endswith("- @ent_babbage: Charles Babbage")
    assert result.model_dump()["related_entities"] == [
        {
            "entity_id": "ent_babbage",
            "name": "Charles Babbage",
            "aliases": ["Babbage"],
            "entity_type": "Person",
            "description": "Inventor and mathematician",
        },
        {
            "entity_id": "ent_analytical_engine",
            "name": "Analytical Engine",
            "aliases": [],
            "entity_type": "node.machine",
            "description": "Related entity Analytical Engine",
        },
    ]

def test_invoke_get_entity_context_requires_knowledge_interface_client() -> None:
    adapters = _adapters()

    try:
        adapters.invoke_get_entity_context(GetEntityContextToolInput.model_validate({"entity_id": "ent_ada"}))
    except RuntimeError as exc:
        assert "knowledge_interface_client" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError when knowledge interface client is missing")
