from __future__ import annotations

from app.adapters.tools.web import TavilyWebAdapter, WebToolError, WebToolsAdapter, load_tavily_clients

# Backwards-compatible aliases while tool provider logic lives in adapter layer.
WebTools = WebToolsAdapter
TavilyWebTools = TavilyWebAdapter

__all__ = ["WebToolError", "WebTools", "TavilyWebTools", "load_tavily_clients"]
