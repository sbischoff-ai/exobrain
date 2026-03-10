import io
from urllib.error import HTTPError

import pytest

from app.adapters.tavily import TavilyClientError, TavilyWebSearchClient
from app.adapters.web_tools import WebSearchAdapter, WebToolError
from app.main import create_web_search_client
from app.settings import Settings


def _settings(**overrides: object) -> Settings:
    base = {
        "APP_ENV": "local",
        "WEB_SEARCH_PROVIDER": "auto",
        "MCP_SERVER_PORT": 8090,
        "MCP_SERVER_HOST": "0.0.0.0",
    }
    base.update(overrides)
    return Settings.model_validate(base)


def test_auto_provider_uses_static_in_local() -> None:
    client = create_web_search_client(_settings(APP_ENV="local", WEB_SEARCH_PROVIDER="auto"))

    from app.adapters.web_tools import StaticWebSearchClient

    assert isinstance(client, StaticWebSearchClient)


def test_auto_provider_uses_tavily_outside_local_test() -> None:
    client = create_web_search_client(
        _settings(APP_ENV="cluster", WEB_SEARCH_PROVIDER="auto", TAVILY_API_KEY="token")
    )

    assert isinstance(client, TavilyWebSearchClient)


def test_tavily_provider_requires_api_key() -> None:
    with pytest.raises(ValueError, match="TAVILY_API_KEY is required"):
        create_web_search_client(_settings(APP_ENV="cluster", WEB_SEARCH_PROVIDER="tavily"))


def test_static_provider_can_be_forced_anywhere() -> None:
    client = create_web_search_client(_settings(APP_ENV="cluster", WEB_SEARCH_PROVIDER="static"))

    from app.adapters.web_tools import StaticWebSearchClient

    assert isinstance(client, StaticWebSearchClient)


def test_tavily_http_error_is_wrapped_as_web_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TavilyWebSearchClient(api_key="bad-key")

    def _raise_http_error(*args, **kwargs):  # noqa: ANN002, ANN003
        _ = args, kwargs
        raise HTTPError(
            url="https://api.tavily.com/search",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"detail":"invalid api key"}'),
        )

    monkeypatch.setattr("app.adapters.tavily.request.urlopen", _raise_http_error)

    adapter = WebSearchAdapter(client=client)
    with pytest.raises(WebToolError, match="status 401"):
        adapter.web_search(
            query="exobrain",
            max_results=3,
            recency_days=None,
            include_domains=None,
            exclude_domains=None,
        )


def test_tavily_search_raises_typed_error_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TavilyWebSearchClient(api_key="key")

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN201
            return None

        def read(self) -> bytes:
            return b"[]"

    monkeypatch.setattr("app.adapters.tavily.request.urlopen", lambda *args, **kwargs: _FakeResponse())

    with pytest.raises(TavilyClientError, match="invalid JSON response"):
        client.search(
            query="exobrain",
            max_results=1,
            recency_days=None,
            include_domains=None,
            exclude_domains=None,
        )
