# Exobrain MCP Server

Python service providing a minimal MCP runtime with strict tool contracts.

## Purpose

- Exposes a process health endpoint for readiness checks.
- Exposes MCP-style tool discovery and invocation endpoints.
- Enforces strict Pydantic request/response schemas for tool inputs/outputs.
- Keeps architecture layered: HTTP transport -> service -> adapters.

## Endpoints and contracts

- `GET /healthz`
  - Readiness check endpoint.
  - Response: `{ "status": "ok" }`
- `GET /mcp/tools`
  - Lists available tools and their input/output JSON schemas.
- `POST /mcp/tools/invoke`
  - Invokes a single tool.
  - Request contract is strict and discriminated by `name`:
    - `echo`: `{ "name": "echo", "arguments": { "text": "..." } }`
    - `add`: `{ "name": "add", "arguments": { "a": 1, "b": 2 } }`
  - Response contract mirrors tool name with typed output:
    - `echo`: `{ "name": "echo", "result": { "text": "..." } }`
    - `add`: `{ "name": "add", "result": { "sum": 3 } }`

## Local run

```bash
cd apps/mcp-server
uv sync --extra dev
uv run uvicorn app.main:app --host 0.0.0.0 --port 8090
```

## Verify

```bash
cd apps/mcp-server
./scripts/verify.sh
```

## Configuration

- `APP_ENV` (default: `local`)
- `LOG_LEVEL` (optional)
- `MCP_SERVER_HOST` (default: `0.0.0.0`)
- `MCP_SERVER_PORT` (default: `8090`)
