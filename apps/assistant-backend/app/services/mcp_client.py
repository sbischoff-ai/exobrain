from __future__ import annotations

import asyncio
import json
import socket
import urllib.error
import urllib.request
from typing import Any

from app.services.contracts import MCPClientProtocol


class MCPClientError(Exception):
    """Base error for MCP client failures."""


class MCPClientInvalidArgumentError(MCPClientError):
    """Raised when MCP server rejects request arguments."""


class MCPClientNotFoundError(MCPClientError):
    """Raised when requested MCP tool or method is not available."""


class MCPClientUnavailableError(MCPClientError):
    """Raised when MCP server is unavailable or times out."""


class MCPClient(MCPClientProtocol):
    """REST HTTP client for MCP tool listing and invocation."""

    def __init__(
        self,
        *,
        base_url: str,
        request_timeout_seconds: float = 5.0,
        max_retries: int = 2,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._request_timeout_seconds = request_timeout_seconds
        self._max_retries = max_retries

    async def close(self) -> None:
        return None

    async def list_tools(self) -> list[dict[str, Any]]:
        response = await self._call(path="/mcp/tools", method="GET")
        tools = response.get("tools") if isinstance(response, dict) else None
        if not isinstance(tools, list):
            return []
        return [tool for tool in tools if isinstance(tool, dict)]

    async def invoke_tool(self, *, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        response = await self._call(
            path="/mcp/tools/invoke",
            method="POST",
            payload={"name": tool_name, "arguments": arguments or {}},
        )
        if not isinstance(response, dict):
            raise MCPClientError("mcp response must be a JSON object")

        if response.get("ok") is False:
            error = response.get("error")
            message = "mcp request failed"
            if isinstance(error, dict) and error.get("message"):
                message = str(error["message"])
            raise MCPClientError(message)

        return response.get("result")

    async def _call(self, *, path: str, method: str, payload: dict[str, Any] | None = None) -> Any:
        for attempt in range(self._max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(self._request_json, path, method, payload),
                    timeout=self._request_timeout_seconds,
                )
            except (asyncio.TimeoutError, TimeoutError, urllib.error.URLError, socket.timeout) as exc:
                if attempt >= self._max_retries:
                    raise MCPClientUnavailableError(f"mcp request failed for {method} {path}") from exc
                await asyncio.sleep(min(0.05 * (2**attempt), 0.25))
            else:
                return response

        raise MCPClientUnavailableError(f"mcp request failed for {method} {path}")

    def _request_json(self, path: str, method: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )

        try:
            with urllib.request.urlopen(request, timeout=self._request_timeout_seconds) as response:
                body = response.read().decode("utf-8")
                status = response.status
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = exc.read().decode("utf-8")

        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise MCPClientError("mcp response must be a JSON object")

        if status == 404:
            raise MCPClientNotFoundError("mcp endpoint not found")
        if status in {400, 422}:
            raise MCPClientInvalidArgumentError("mcp request arguments are invalid")
        if status >= 500:
            raise MCPClientUnavailableError("mcp server unavailable")
        return parsed
