# Exobrain MCP Server

Python service providing a minimal MCP runtime with strict tool contracts.

## Purpose

- Exposes a process health endpoint for readiness checks.
- Exposes MCP-style tool discovery and invocation endpoints.
- Enforces strict Pydantic request/response schemas for tool inputs/outputs.
- Keeps architecture layered: HTTP transport -> service -> adapters.
- Centralizes tool registration in `app/adapters/tool_registry.py` (metadata, parser, handler).
- Hosts migrated web-search adapter logic with provider clients hidden behind interfaces.

## Endpoints and contracts

The runtime exposes an HTTP REST transport for MCP tool operations. It does **not** expose a JSON-RPC endpoint.

- `GET /healthz`
  - Readiness check endpoint.
  - Response: `{ "status": "ok" }`
- `GET /mcp/tools`
  - Lists available tools and their input JSON schemas in `inputSchema` (camelCase).
- `POST /mcp/tools/invoke`
  - Invokes a single tool with a typed invocation envelope:
    - `name`: tool identifier
    - `arguments`: tool-specific payload
    - `metadata` (optional): correlation/request IDs
  - Typed result envelope:
    - success: `{ "ok": true, "name": "...", "result": {...}, "metadata": {...} }`
    - error: `{ "ok": false, "name": "...", "error": {"code": "...", "message": "..."}, "metadata": {...} }`

### Canonical request/response examples

`GET /mcp/tools`

```json
{
  "tools": [
    {
      "name": "web_search",
      "description": "Search the web for relevant results",
      "inputSchema": {
        "type": "object",
        "properties": {
          "query": {"type": "string"},
          "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
          "recency_days": {"type": "integer", "minimum": 1}
        },
        "required": ["query"],
        "additionalProperties": false
      }
    }
  ]
}
```

`POST /mcp/tools/invoke` request body:

```json
{
  "name": "web_fetch",
  "arguments": {
    "url": "https://example.com",
    "max_chars": 4000
  },
  "metadata": {
    "correlation_id": "chat-123",
    "request_id": "req-456"
  }
}
```

Success response body:

```json
{
  "ok": true,
  "name": "web_fetch",
  "result": {
    "url": "https://example.com",
    "title": "Example Domain",
    "content_text": "...",
    "extracted_at": "2026-03-01T10:30:00Z",
    "content_truncated": false
  },
  "metadata": {
    "correlation_id": "chat-123",
    "request_id": "req-456"
  }
}
```

Error response body:

```json
{
  "ok": false,
  "name": "web_fetch",
  "error": {
    "code": "TOOL_INVOCATION_ERROR",
    "message": "failed to fetch url"
  },
  "metadata": {
    "correlation_id": "chat-123",
    "request_id": "req-456"
  }
}
```

### Contract source of truth

Canonical MCP HTTP contract types are defined in `apps/mcp-server/app/contracts/`:

- `tools.py`: list-tools and invoke request/response envelopes.
- `health.py`: health endpoint response schema.
- `base.py`: strict schema base model (`extra="forbid"`).

### Tool registration and dispatch

Tool wiring is centralized in `app/adapters/tool_registry.py`. Each registry entry defines:

- `name`
- `metadata_provider` (description + JSON schema)
- `invocation_parser` (per-tool Pydantic validation)
- `handler` function

`ToolService` uses registry lookup/dispatch instead of per-tool branching.

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
- `WEB_SEARCH_PROVIDER` (`auto` | `static` | `tavily`, default: `auto`)
- `TAVILY_API_KEY` (required when provider resolves to `tavily`)
- `TAVILY_BASE_URL` (default: `https://api.tavily.com`)

### Web search runtime modes

- `WEB_SEARCH_PROVIDER=auto`:
  - `APP_ENV=local` or `APP_ENV=test` uses `StaticWebSearchClient` (deterministic local/test behavior).
  - all other environments use Tavily.
- `WEB_SEARCH_PROVIDER=static`: always uses `StaticWebSearchClient`.
- `WEB_SEARCH_PROVIDER=tavily`: always uses Tavily and requires `TAVILY_API_KEY`.
