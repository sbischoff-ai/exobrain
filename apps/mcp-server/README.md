# Exobrain MCP Server

Python service providing a minimal MCP runtime with strict tool contracts.

## Purpose

- Exposes a process health endpoint for readiness checks.
- Exposes MCP-style tool discovery and invocation endpoints.
- Enforces strict Pydantic request/response schemas for tool inputs/outputs.
- Keeps architecture layered: HTTP transport -> service -> adapters.
- Splits tool registrations by category in adapter registry builders (`utility`, `web`, extensible to future categories).
- Composes enabled tool categories and feature flags from settings in `app.main:create_tool_registry`.
- Hosts migrated web-search adapter logic with provider clients hidden behind interfaces.

## Endpoints and contracts

The runtime exposes an HTTP REST transport for MCP tool operations. It does **not** expose a JSON-RPC endpoint.

- `GET /healthz`
  - Readiness check endpoint.
  - Response: `{ "status": "ok" }`
- `GET /mcp/tools`
  - Lists available tools and their input JSON schemas in `inputSchema` (camelCase).
  - Includes `resolve_entities` when the `knowledge` category is enabled and `ENABLE_KNOWLEDGE_TOOLS=true`.
- `POST /mcp/tools/invoke`
  - Invokes a single tool with a typed invocation envelope:
    - `name`: tool identifier
    - `arguments`: tool-specific payload
    - `metadata` (optional): correlation/request IDs
  - Typed result envelope:
    - success: `{ "ok": true, "name": "...", "result": {...}, "metadata": {...} }`
    - error: `{ "ok": false, "name": "...", "error": {"code": "...", "message": "..."}, "metadata": {...} }`

## Tool contracts

The complete catalog of available tools and their request/response contracts is documented in:

- [`docs/tool-contracts.md`](docs/tool-contracts.md)

That document includes:

- Discovery metadata shape (`GET /mcp/tools` output)
- Invocation envelope and error envelope contracts (`POST /mcp/tools/invoke`)
- Input and output field-level constraints for every currently registered tool:
  - `echo`
  - `add`
  - `web_search`
  - `web_fetch`
  - `resolve_entities`
  - `get_entity_context`

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

`ToolRegistration` remains the central contract in `app/adapters/tool_registry.py`. Each registration defines:

- `name`
- `category`
- `metadata_provider` (description + JSON schema)
- `invocation_parser` (per-tool Pydantic validation)
- `handler` function
- optional `feature_flag` settings gate
- optional `dependencies` declaration for external/runtime requirements

Category-specific builders live under `app/adapters/*_registry_builder.py` and are composed by `create_tool_registry` using `ENABLED_TOOL_CATEGORIES` plus per-category feature flags.

`ToolService` uses registry lookup/dispatch instead of per-tool branching and returns:

- one generic success envelope for all tools (built-in and dynamically registered)
  - `resolve_entities` currently returns deterministic placeholder resolution data in local/test flows (no external service dependency).
- typed error envelopes for failures

## Local run

```bash
cd apps/mcp-server
cp .env.example .env
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
- `ENABLED_TOOL_CATEGORIES` (comma-delimited, default: `utility,knowledge,web`)
- `ENABLE_UTILITY_TOOLS` (default: `false`)
- `ENABLE_WEB_TOOLS` (default: `true`)
- `ENABLE_KNOWLEDGE_TOOLS` (default: `true`)
- `TAVILY_API_KEY` (required when provider resolves to `tavily`)
- `TAVILY_BASE_URL` (default: `https://api.tavily.com`)

### Web search runtime modes

- `WEB_SEARCH_PROVIDER=auto`:
  - uses Tavily whenever `TAVILY_API_KEY` is set (including `APP_ENV=local` and `APP_ENV=test`).
  - falls back to `StaticWebSearchClient` only for `APP_ENV=local` or `APP_ENV=test` when no `TAVILY_API_KEY` is configured.
  - requires `TAVILY_API_KEY` in all other environments.
- `WEB_SEARCH_PROVIDER=static`: always uses `StaticWebSearchClient`.
- `WEB_SEARCH_PROVIDER=tavily`: always uses Tavily and requires `TAVILY_API_KEY`.
