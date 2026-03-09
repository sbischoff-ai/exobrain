from __future__ import annotations

import asyncio
import json
import socket
import urllib.error
import urllib.request
from typing import Any
from uuid import uuid4

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
    """JSON-RPC HTTP client for MCP tool listing and invocation."""

    def __init__(
        self,
        *,
        base_url: str,
        request_timeout_seconds: float = 5.0,
        max_retries: int = 2,
    ) -> None:
        self._base_url = base_url
        self._request_timeout_seconds = request_timeout_seconds
        self._max_retries = max_retries

    async def close(self) -> None:
        return None

    async def list_tools(self) -> list[dict[str, Any]]:
        response = await self._call(method="tools/list", params={})
        tools = response.get("tools") if isinstance(response, dict) else None
        if not isinstance(tools, list):
            return []
        return [tool for tool in tools if isinstance(tool, dict)]

    async def invoke_tool(self, *, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        return await self._call(
            method="tools/call",
            params={"name": tool_name, "arguments": arguments or {}},
        )

    async def _call(self, *, method: str, params: dict[str, Any]) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": method,
            "params": params,
        }

        for attempt in range(self._max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(self._post_json, payload),
                    timeout=self._request_timeout_seconds,
                )
                return self._parse_response(response)
            except (asyncio.TimeoutError, TimeoutError, urllib.error.URLError, socket.timeout) as exc:
                if attempt >= self._max_retries:
                    raise MCPClientUnavailableError(f"mcp request failed for {method}") from exc
                await asyncio.sleep(min(0.05 * (2**attempt), 0.25))

        raise MCPClientUnavailableError(f"mcp request failed for {method}")

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self._base_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self._request_timeout_seconds) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise MCPClientError("mcp response must be a JSON object")
        return parsed

    def _parse_response(self, response: dict[str, Any]) -> Any:
        error = response.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            message = str(error.get("message") or "mcp request failed")
            if code == -32601:
                raise MCPClientNotFoundError(message)
            if code == -32602:
                raise MCPClientInvalidArgumentError(message)
            if code in {-32000, -32001, -32002}:
                raise MCPClientUnavailableError(message)
            raise MCPClientError(message)

        return response.get("result")
