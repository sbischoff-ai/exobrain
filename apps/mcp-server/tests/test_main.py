from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_tools() -> None:
    response = client.get("/mcp/tools")

    assert response.status_code == 200
    body = response.json()
    assert [tool["name"] for tool in body["tools"]] == ["echo", "add", "web_search"]


def test_invoke_echo_tool() -> None:
    response = client.post(
        "/mcp/tools/invoke",
        json={"name": "echo", "arguments": {"text": "hello"}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "name": "echo",
        "result": {"text": "hello"},
        "metadata": None,
    }


def test_invoke_add_tool() -> None:
    response = client.post(
        "/mcp/tools/invoke",
        json={"name": "add", "arguments": {"a": 2, "b": 3}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "name": "add",
        "result": {"sum": 5},
        "metadata": None,
    }


def test_invoke_web_search_tool() -> None:
    response = client.post(
        "/mcp/tools/invoke",
        json={"name": "web_search", "arguments": {"query": "exobrain"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["name"] == "web_search"
    assert len(body["result"]["results"]) == 1


def test_invoke_tool_rejects_invalid_arguments() -> None:
    response = client.post(
        "/mcp/tools/invoke",
        json={"name": "add", "arguments": {"a": 2, "b": "nope"}},
    )

    assert response.status_code == 422
