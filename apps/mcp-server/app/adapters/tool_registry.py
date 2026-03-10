from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.contracts import ToolMetadata


@dataclass(frozen=True)
class ToolRegistration:
    """Canonical registration contract for every tool.

    Conventions:
    - category: stable group identifier (for example: utility, web)
    - feature_flag: optional settings field name that gates this tool
    - dependencies: external provider/runtime dependencies required by this tool
    """

    name: str
    category: str
    metadata_provider: Callable[[], ToolMetadata]
    invocation_parser: Callable[[dict[str, Any]], Any]
    handler: Callable[[Any], Any]
    error_code: str | None = None
    feature_flag: str | None = None
    dependencies: tuple[str, ...] = ()

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


def schema_metadata(name: str, description: str, parser: type) -> Callable[[], ToolMetadata]:
    def _provide() -> ToolMetadata:
        return ToolMetadata(name=name, description=description, inputSchema=parser.model_json_schema())

    return _provide


def input_parser(model: type) -> Callable[[dict[str, Any]], Any]:
    def _parse(arguments: dict[str, Any]) -> Any:
        return model.model_validate(arguments)

    return _parse
