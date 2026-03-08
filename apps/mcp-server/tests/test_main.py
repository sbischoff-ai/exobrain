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
    assert [tool["name"] for tool in body["tools"]] == ["echo", "add"]


def test_invoke_echo_tool() -> None:
    response = client.post(
        "/mcp/tools/invoke",
        json={"name": "echo", "arguments": {"text": "hello"}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "name": "echo",
        "result": {"text": "hello"},
    }


def test_invoke_add_tool() -> None:
    response = client.post(
        "/mcp/tools/invoke",
        json={"name": "add", "arguments": {"a": 2, "b": 3}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "name": "add",
        "result": {"sum": 5},
    }


def test_invoke_tool_rejects_invalid_arguments() -> None:
    response = client.post(
        "/mcp/tools/invoke",
        json={"name": "add", "arguments": {"a": 2, "b": "nope"}},
    )

    assert response.status_code == 422
