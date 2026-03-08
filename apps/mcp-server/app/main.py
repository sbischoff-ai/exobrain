from __future__ import annotations

from fastapi import FastAPI

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.services.tool_service import ToolService
from app.settings import get_settings
from app.transport.http.routes import build_router

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(title="exobrain-mcp-server", version="0.1.0")

    tool_service = ToolService(registry=ToolAdapterRegistry())
    app.include_router(build_router(tool_service))

    return app


app = create_app()
