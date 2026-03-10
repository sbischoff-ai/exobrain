from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.contracts import (
    AddToolInput,
    EchoToolInput,
    ToolMetadata,
    WebFetchToolInput,
    WebSearchToolInput,
)


@dataclass(frozen=True)
class ToolRegistration:
    name: str
    metadata_provider: Callable[[], ToolMetadata]
    invocation_parser: Callable[[dict[str, Any]], Any]
    handler: Callable[[Any], Any]
    error_code: str | None = None

    def metadata(self) -> ToolMetadata:
        return self.metadata_provider()

    def parse_arguments(self, payload: dict[str, Any]) -> Any:
        return self.invocation_parser(payload)


class ToolRegistry:
    def __init__(self, registrations: list[ToolRegistration]):
        self._registrations = {registration.name: registration for registration in registrations}

    def list_tools(self) -> list[ToolMetadata]:
        return [registration.metadata() for registration in self._registrations.values()]

    def get(self, name: str) -> ToolRegistration | None:
        return self._registrations.get(name)

    def registrations(self) -> list[ToolRegistration]:
        return list(self._registrations.values())


def _schema_metadata(name: str, description: str, parser: type) -> Callable[[], ToolMetadata]:
    def _provide() -> ToolMetadata:
        return ToolMetadata(name=name, description=description, inputSchema=parser.model_json_schema())

    return _provide


def _input_parser(model: type) -> Callable[[dict[str, Any]], Any]:
    def _parse(arguments: dict[str, Any]) -> Any:
        return model.model_validate(arguments)

    return _parse


def build_tool_registry(adapters: ToolAdapterRegistry) -> ToolRegistry:
    registrations = [
        ToolRegistration(
            name="echo",
            metadata_provider=_schema_metadata("echo", "Return the input text.", EchoToolInput),
            invocation_parser=_input_parser(EchoToolInput),
            handler=adapters.invoke_echo,
        ),
        ToolRegistration(
            name="add",
            metadata_provider=_schema_metadata("add", "Add two integers.", AddToolInput),
            invocation_parser=_input_parser(AddToolInput),
            handler=adapters.invoke_add,
        ),
        ToolRegistration(
            name="web_search",
            metadata_provider=_schema_metadata(
                "web_search",
                "Search the web for candidate sources and return normalized title/url/snippet metadata.",
                WebSearchToolInput,
            ),
            invocation_parser=_input_parser(WebSearchToolInput),
            handler=adapters.invoke_web_search,
            error_code="WEB_SEARCH_FAILED",
        ),
        ToolRegistration(
            name="web_fetch",
            metadata_provider=_schema_metadata(
                "web_fetch",
                "Fetch readable plaintext from a URL and return normalized content metadata.",
                WebFetchToolInput,
            ),
            invocation_parser=_input_parser(WebFetchToolInput),
            handler=adapters.invoke_web_fetch,
            error_code="WEB_FETCH_FAILED",
        ),
    ]

    return ToolRegistry(registrations=registrations)
