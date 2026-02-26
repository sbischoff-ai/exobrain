import importlib


def test_format_stream_error_returns_sse_error_payload(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    main = importlib.import_module("app.main")
    error = main.ProviderClientError(status_code=400, message="bad request")
    event = main._format_stream_error(error, alias="agent", provider="openai")

    assert event.startswith("data: ")
    assert '"code": 400' in event
    assert 'provider=openai alias=agent' in event
