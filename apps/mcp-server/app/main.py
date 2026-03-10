from __future__ import annotations

from fastapi import FastAPI

from app.adapters.tavily import TavilyWebSearchClient
from app.adapters.tool_adapters import ToolAdapterRegistry
from app.adapters.tool_registry import build_tool_registry
from app.adapters.web_tools import StaticWebSearchClient, WebFetchAdapter, WebSearchAdapter
from app.services.tool_service import ToolService
from app.settings import Settings, get_settings
from app.transport.http.routes import build_router

settings = get_settings()


def create_web_search_client(settings: Settings) -> StaticWebSearchClient | TavilyWebSearchClient:
    provider = settings.web_search_provider.lower()

    if provider == "static":
        return StaticWebSearchClient()

    use_static_for_local = provider == "auto" and settings.app_env.lower() in {"local", "test"}
    if use_static_for_local:
        return StaticWebSearchClient()

    if provider not in {"auto", "tavily"}:
        raise ValueError(f"Unsupported WEB_SEARCH_PROVIDER: {settings.web_search_provider}")

    if not settings.tavily_api_key:
        raise ValueError("TAVILY_API_KEY is required when WEB_SEARCH_PROVIDER resolves to tavily")

    return TavilyWebSearchClient(api_key=settings.tavily_api_key, base_url=settings.tavily_base_url)


def create_app(app_settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="exobrain-mcp-server", version="0.1.0")

    resolved_settings = app_settings or settings
    web_client = create_web_search_client(resolved_settings)
    web_search_adapter = WebSearchAdapter(client=web_client)
    web_fetch_adapter = WebFetchAdapter(client=web_client)
    adapters = ToolAdapterRegistry(web_search_adapter=web_search_adapter, web_fetch_adapter=web_fetch_adapter)
    tool_service = ToolService(registry=build_tool_registry(adapters))
    app.include_router(build_router(tool_service))

    return app


app = create_app()
