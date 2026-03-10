from __future__ import annotations

import json
from typing import Any
from urllib import error, request


class TavilyClientError(RuntimeError):
    """Raised when Tavily returns an error response."""


class TavilyWebSearchClient:
    def __init__(self, *, api_key: str, base_url: str = "https://api.tavily.com"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def search(
        self,
        *,
        query: str,
        max_results: int,
        recency_days: int | None,
        include_domains: list[str] | None,
        exclude_domains: list[str] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }
        if recency_days is not None:
            payload["days"] = recency_days
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains

        return self._post_json("/search", payload)

    def extract(self, *, url: str) -> dict[str, Any]:
        payload = {
            "api_key": self._api_key,
            "urls": [url],
            "extract_depth": "basic",
        }
        return self._post_json("/extract", payload)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        raw_payload = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self._base_url}{path}",
            data=raw_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise TavilyClientError(f"tavily request failed with status {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise TavilyClientError(f"tavily request failed: {exc.reason}") from exc

        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise TavilyClientError("tavily request failed: invalid JSON response")
        return parsed
