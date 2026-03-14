from __future__ import annotations

import asyncio
import json
import logging
import socket
import urllib.error
import urllib.request
from typing import Any

from app.services.contracts import MCPClientProtocol

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """Base error for MCP client failures."""


class MCPClientInvalidArgumentError(MCPClientError):
    """Raised when MCP server rejects request arguments."""


class MCPClientNotFoundError(MCPClientError):
    """Raised when requested MCP tool or method is not available."""


class MCPClientUnavailableError(MCPClientError):
    """Raised when MCP server is unavailable or times out."""


class MCPClientUnauthorizedError(MCPClientError):
    """Raised when MCP server rejects authentication/authorization."""


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

    async def list_tools(self, *, access_token: str | None = None, session_id: str | None = None) -> list[dict[str, Any]]:
        response = await self._call(path="/mcp/tools", method="GET", access_token=access_token, session_id=session_id)
        tools = response.get("tools") if isinstance(response, dict) else None
        if not isinstance(tools, list):
            return []
        return [tool for tool in tools if isinstance(tool, dict)]

    async def invoke_tool(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        access_token: str | None = None,
        session_id: str | None = None,
    ) -> Any:
        tool_path = "/mcp/tools/invoke"
        try:
            response = await self._call(
                path=tool_path,
                method="POST",
                payload={"name": tool_name, "arguments": arguments or {}},
                access_token=access_token,
                session_id=session_id,
            )
        except MCPClientError:
            logger.exception("mcp invoke_tool request failed", extra={"tool_name": tool_name, "path": tool_path})
            raise

        if not isinstance(response, dict):
            logger.error(
                "mcp invoke_tool received invalid response",
                extra={"tool_name": tool_name, "path": tool_path, "response_type": type(response).__name__},
            )
            raise MCPClientError("mcp response must be a JSON object")

        ok = response.get("ok") if "ok" in response else None
        if not isinstance(ok, bool):
            logger.error(
                "mcp invoke_tool response envelope invalid",
                extra={"tool_name": tool_name, "path": tool_path},
            )
            raise MCPClientError("mcp response envelope invalid: expected boolean 'ok'")

        if ok is False:
            error = response.get("error")
            message = "mcp request failed"
            if isinstance(error, dict) and error.get("message"):
                message = str(error["message"])
            logger.error(
                "mcp invoke_tool returned error response",
                extra={"tool_name": tool_name, "path": tool_path, "error_message": message},
            )
            raise MCPClientError(message)

        return response.get("result")

    async def _call(
        self,
        *,
        path: str,
        method: str,
        payload: dict[str, Any] | None = None,
        access_token: str | None = None,
        session_id: str | None = None,
    ) -> Any:
        for attempt in range(self._max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(self._request_json, path, method, payload, access_token, session_id),
                    timeout=self._request_timeout_seconds,
                )
            except (asyncio.TimeoutError, TimeoutError, urllib.error.URLError, socket.timeout) as exc:
                if attempt >= self._max_retries:
                    raise MCPClientUnavailableError(f"mcp request failed for {method} {path}") from exc
                await asyncio.sleep(min(0.05 * (2**attempt), 0.25))
            else:
                return response

        raise MCPClientUnavailableError(f"mcp request failed for {method} {path}")

    def _request_json(
        self,
        path: str,
        method: str,
        payload: dict[str, Any] | None,
        access_token: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        elif session_id:
            headers["x-session-id"] = session_id

        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=data,
            headers=headers,
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
        if status in {401, 403}:
            raise MCPClientUnauthorizedError("mcp request unauthorized")
        if status in {400, 422}:
            raise MCPClientInvalidArgumentError(self._build_invalid_argument_message(parsed))
        if status >= 500:
            raise MCPClientUnavailableError("mcp server unavailable")
        if status < 200 or status >= 300:
            raise MCPClientError(f"mcp request failed with unexpected status {status}")
        return parsed

    @staticmethod
    def _build_invalid_argument_message(parsed: dict[str, Any]) -> str:
        base_message = "mcp request arguments are invalid"
        detail = parsed.get("detail")
        if detail is None:
            return base_message

        if isinstance(detail, str):
            cleaned = detail.strip()
            if cleaned:
                return f"{base_message}: {cleaned}"
            return base_message

        if isinstance(detail, list):
            entries: list[str] = []
            for item in detail:
                if isinstance(item, str):
                    cleaned_item = item.strip()
                    if cleaned_item:
                        entries.append(cleaned_item)
                    continue

                if not isinstance(item, dict):
                    continue
                item_message = item.get("msg") or item.get("message")
                if not item_message:
                    continue
                loc = item.get("loc")
                if isinstance(loc, list):
                    loc_label = ".".join(str(part) for part in loc)
                else:
                    loc_label = ""
                if loc_label:
                    entries.append(f"{loc_label}: {item_message}")
                else:
                    entries.append(str(item_message))

            if entries:
                return f"{base_message}: {'; '.join(entries)}"

        if isinstance(detail, dict):
            detail_message = detail.get("message") or detail.get("msg")
            if detail_message:
                return f"{base_message}: {detail_message}"

        return base_message
