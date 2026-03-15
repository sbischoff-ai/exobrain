# Exobrain Assistant Backend

FastAPI service for auth, chat orchestration, journal APIs, and knowledge-base update workflows. Includes `/api/knowledge/update` to enqueue updates, `/api/knowledge/update/{job_id}/watch` to stream lifecycle events via SSE from job-orchestrator, `/api/knowledge/category/{category_id}/pages` for category page listings backed by `ListEntitiesByType`, and `/api/knowledge/page/{page_id}` for page detail backed by `GetEntityContext`, plus `PATCH /api/knowledge/page/{page_id}` for block markdown updates via `UpsertGraphDelta`.

Knowledge update stream contract: [`docs/knowledge-update-sse-contract.md`](docs/knowledge-update-sse-contract.md).

Knowledge category/page contract: [`docs/knowledge-category-page-contract.md`](docs/knowledge-category-page-contract.md).

Chat/MCP auth propagation: when `/api/chat/message` is authenticated via bearer token, that same token is threaded through the chat stream lifecycle and sent to MCP tool calls as `Authorization: Bearer <token>`. For session-authenticated requests without a bearer token, the backend mints a short-lived access token from the authenticated principal and sends it as `Authorization: Bearer <token>` for MCP tool calls.

## What this service is

The backend follows layered boundaries:

- API layer (`app/api`) for request/response wiring.
- Service layer (`app/services`) for use-case orchestration.
- Agent layer (`app/agents`) for model + tool integrations.
- DI container (`app/dependency_injection`) resolves app services from `app.state.container`.

Cross-service standards are documented in [`../../docs/standards/engineering-standards.md`](../../docs/standards/engineering-standards.md).

## Quick start

For canonical local startup/orchestration:

- [`../../docs/development/local-setup.md`](../../docs/development/local-setup.md)
- [`../../docs/development/process-orchestration.md`](../../docs/development/process-orchestration.md)

Service-only run:

```bash
./scripts/local/build-assistant-backend.sh
./scripts/local/run-assistant-backend.sh
```

## Common commands

Database setup:

```bash
./scripts/local/assistant-db-setup.sh
```

Unit tests:

```bash
cd apps/assistant-backend && uv run --with pytest --with pytest-asyncio pytest
```

Integration tests:

```bash
cd apps/assistant-backend
ASSISTANT_BACKEND_INTEGRATION_ENV_FILE=tests/integration/.env.integration \
  uv run --with pytest --with pytest-asyncio --with httpx pytest -m integration
```

MCP bridge integration coverage (assistant `build_mcp_tools` + mounted `apps/mcp-server` app):

```bash
cd apps/assistant-backend && uv run --extra dev pytest tests/integration/test_mcp_tool_bridge_integration.py
```

Run static checks + tests together:

```bash
cd apps/assistant-backend && ./scripts/verify.sh
```

## Seed Memgraph test data for assistant-backend

Use the canned knowledge-interface gRPC payloads to initialize graph state for the seeded assistant-backend test user (`test.user@exobrain.local`) and upsert a realistic task + block tree for GraphRAG testing.

```bash
./scripts/local/add-assistant-backend-memgraph-test-data.sh
```

The script reads:

- `apps/knowledge-interface/mock-data/knowledge/initialize-user-graph.request.json`
- `apps/knowledge-interface/mock-data/knowledge/upsert-graph-delta.request.template.json`

Optional overrides:

- `KNOWLEDGE_GRPC_TARGET` (default `127.0.0.1:50051`)
- `INIT_REQUEST_PATH`
- `DELTA_TEMPLATE_PATH`


## Knowledge category/page endpoints

### `GET /api/knowledge/category`
Returns active wiki categories rooted at direct `node.entity` subtypes (excluding `node.block` and `node.universe`), then nests descendant subtypes.

Example response:

```json
{
  "categories": [
    {
      "category_id": "node.root",
      "display_name": "Root",
      "sub_categories": [
        {
          "category_id": "node.child",
          "display_name": "Child",
          "sub_categories": []
        }
      ]
    }
  ]
}
```

### `GET /api/knowledge/category/{category_id}/pages`
Returns paginated page summaries for a category via `ListEntitiesByType`.

Example response:

```json
{
  "knowledge_pages": [
    {
      "id": "entity-1",
      "title": "Entity One",
      "summary": "Entity summary",
      "metadata": {
        "created_at": "",
        "updated_at": "2026-02-19T10:00:00Z"
      }
    }
  ],
  "page_size": 20,
  "next_page_token": "next-cursor",
  "total_count": 42
}
```

### `GET /api/knowledge/page/{page_id}`
Returns page detail via `GetEntityContext`, including canonical metadata timestamps, filtered entity-type properties, related links, and ordered `content_blocks` (`block_id` + `markdown`).

Example response:

```json
{
  "id": "entity-1",
  "category_id": "node.task",
  "title": "Entity One",
  "summary": "Entity summary",
  "metadata": {
    "created_at": "2026-02-19T09:00:00Z",
    "updated_at": "2026-02-19T10:00:00Z"
  },
  "properties": {
    "status": "in_progress",
    "priority": "high"
  },
  "links": [
    {
      "page_id": "entity-2",
      "title": "Entity Two",
      "summary": "Linked summary"
    }
  ],
  "content_blocks": [{"block_id": "b1", "markdown": "Root"}, {"block_id": "b2", "markdown": "Child"}]
}
```

Notes:

- `properties` includes only entity-type-specific fields from upstream `entity_properties`; reserved/system keys (`created_at`, `updated_at`, `visibility`, `user_id`, `type_id`, `id`) are excluded.
- `created_at` and `updated_at` are still surfaced under `metadata` for timestamp rendering.
- `content_blocks` preserves upstream block order; frontend renders each markdown block independently and in sequence so existing visual output remains unchanged while supporting multi-block pages.

### `PATCH /api/knowledge/page/{page_id}`
Updates existing page `content_blocks` markdown using `UpsertGraphDelta` block upserts.

Request:

```json
{
  "content_blocks": [
    {"block_id": "b1", "markdown_content": "# Updated"},
    {"block_id": "b2", "markdown_content": "Body"}
  ]
}
```

Response:

```json
{
  "page_id": "entity-1",
  "updated_block_ids": ["b1", "b2"],
  "updated_block_count": 2,
  "status": "updated"
}
```

Error mapping: `400` invalid payload/block ids, `403` access denied, `404` page missing, `503` upstream unavailable/timeouts, `502` unexpected upstream failures.

## User config endpoints

### `GET /api/users/me/configs`
Returns all effective user configs for the authenticated user, including each config key, display name, config type (`boolean` or `choice`), allowed options for choice configs, current effective value, and default fallback metadata. Config definitions/options are loaded from Postgres and merged with per-user overrides.

Example response:

```json
{
  "configs": [
    {
      "key": "frontend.theme",
      "name": "Theme",
      "config_type": "choice",
      "description": "Controls the interface theme used in assistant clients",
      "options": [
        {"value": "gruvbox-dark", "label": "Gruvbox Dark"},
        {"value": "purple-intelligence", "label": "Purple Intelligence"}
      ],
      "value": "purple-intelligence",
      "default_value": "gruvbox-dark",
      "using_default": false
    },
    {
      "key": "daily_digest_enabled",
      "name": "Daily Digest",
      "config_type": "boolean",
      "description": "Enable daily digest reminders in assistant experiences",
      "options": [],
      "value": true,
      "default_value": true,
      "using_default": true
    }
  ]
}
```

### `PATCH /api/users/me/configs`
Accepts one or more config updates in a single request and returns the full effective config list after validation and update application. Boolean updates must be strict `true`/`false`, choice updates must match configured options, and writes are applied atomically.

Single-update example:

```json
{
  "update": {
    "key": "frontend.theme",
    "value": "purple-intelligence"
  }
}
```

Batch-update example:

```json
{
  "updates": [
    {"key": "frontend.theme", "value": "gruvbox-dark"},
    {"key": "daily_digest_enabled", "value": false}
  ]
}
```

Validation/default semantics:

- Unknown config keys return `400`.
- Choice values must be one of the configured `options[].value` values or the request returns `400`.
- Boolean values must be JSON booleans (`true`/`false`), not strings.
- Effective values are computed as `override if present else default_value`.
- If a submitted value matches the definition's default value, any stored override is removed and `using_default` becomes `true` in subsequent reads.

## Configuration

Core runtime vars:

- `ASSISTANT_DB_DSN` (Postgres metastore)
- `ASSISTANT_CACHE_REDIS_URL` (session store)
- `JOB_ORCHESTRATOR_GRPC_TARGET` (required orchestrator `EnqueueJob` gRPC endpoint, default `localhost:50061`; examples: local dev/codex `localhost:50061`, Kubernetes `exobrain-job-orchestrator-api:50061`)
- Knowledge update requests do **not** publish to NATS directly from assistant-backend. The backend calls orchestrator `EnqueueJob` with `user_id`, `job_type=knowledge.update`, and a typed payload containing `journal_reference`, message entries, and `requested_by_user_id`.
- `JOB_ORCHESTRATOR_CONNECT_TIMEOUT_SECONDS` (gRPC request timeout in seconds, default `5.0`)
- `KNOWLEDGE_INTERFACE_GRPC_TARGET` (knowledge-interface gRPC endpoint for read APIs, default `localhost:50051`)
- `KNOWLEDGE_INTERFACE_CONNECT_TIMEOUT_SECONDS` (knowledge-interface gRPC request timeout in seconds, default `5.0`)
- `MCP_SERVER_URL` (MCP HTTP base URL used by assistant tool calls, default `http://localhost:8090` (client calls `/mcp/tools` and `/mcp/tools/invoke`))
- `MCP_REQUEST_TIMEOUT_SECONDS` (MCP tool list/invoke timeout in seconds, default `5.0`)
- `MCP_MAX_RETRIES` (MCP retry attempts for timeout/transient transport failures, default `2`)
- Knowledge wiki category trees are derived from active `GetSchema` node types (`kind=node`, ids prefixed `node.`), rooted at direct children of `node.entity` (excluding `node.block` and `node.universe`), and sorted by `display_name` then `id`.
- `GET /api/knowledge/category` maps upstream `INVALID_ARGUMENT` to `400`, `UNAVAILABLE/DEADLINE_EXCEEDED` to `503`, and other upstream failures to `502`.
- Multiple inheritance in wiki categories duplicates a child category under each active parent category.
- `POST /api/knowledge/update` returns `409` when there are no uncommitted messages in scope, `503` when orchestrator is unavailable, and `502` for other enqueue failures.
- `GET /api/knowledge/category/{category_id}/pages` accepts `page_size` and `page_token`, and maps upstream `INVALID_ARGUMENT` to `400`, `UNAVAILABLE/DEADLINE_EXCEEDED` to `503`, and other upstream failures to `502`.
- `GET /api/knowledge/page/{page_id}` calls `GetEntityContext` with `max_block_level=2`, maps `NOT_FOUND` to `404`, `PERMISSION_DENIED/UNAUTHENTICATED` to `403`, `UNAVAILABLE/DEADLINE_EXCEEDED` to `503`, and other upstream failures to `502`.
- `EXOBRAIN_QDRANT_URL`, `EXOBRAIN_MEMGRAPH_URL` (knowledge dependencies)
- `KNOWLEDGE_UPDATE_MAX_TOKENS` (max tokens per knowledge-update job payload, default `8000`)
- `RESHAPE_SCHEMA_QUERY` (migration introspection)

Model/tool vars:

- Main agent prompt includes markdown rendering guidance for math and diagrams (`$...$`, `$$...$$`, and ```mermaid fenced blocks; display math is expected on its own lines).
- `MAIN_AGENT_USE_MOCK=true|false`
- `MAIN_AGENT_MOCK_MESSAGES_FILE`
- `MODEL_PROVIDER_BASE_URL` (default `http://localhost:8010/v1`; clients append `/internal/chat/messages` to this base URL)
- `MAIN_AGENT_MODEL_CONTRACT_MODE=native|legacy_openai_compatible` (default `native`; `native` uses `ModelProviderChatModel` with the internal `/v1/internal/chat/messages` contract, `legacy_openai_compatible` uses `ChatOpenAI` against the OpenAI-compatible endpoint shape)
- `MAIN_AGENT_USE_OPENAI_FALLBACK=true|false` (rollout safety flag; when `true`, force `ChatOpenAI` compatibility mode even if contract mode is `native`)
- `MAIN_AGENT_MODEL` (alias, default `agent`)
- Agent tools are discovered from MCP `GET /mcp/tools` and executed via `POST /mcp/tools/invoke`; tool lifecycle SSE events still map known tool names (`web_search`, `web_fetch`) to user-facing progress updates.

## MCP tool HTTP contract

assistant-backend integrates with mcp-server over HTTP REST. The integration contract is request/response JSON over `/mcp/tools` and `/mcp/tools/invoke` (not JSON-RPC). Tool metadata uses `inputSchema` (camelCase) as the canonical input schema field.
When tool metadata includes JSON Schema defaults for optional arguments, assistant-backend applies those defaults before invoking the MCP tool so omitted optionals still satisfy the server contract.

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

Canonical MCP HTTP contract types live in `apps/mcp-server/app/contracts/` and are owned by the mcp-server service.


OpenAPI and logging:

- `APP_ENV=local` enables `/docs`; non-local disables OpenAPI docs.
- `LOG_LEVEL` overrides defaults (`DEBUG` local, `INFO` otherwise).

## Enqueue flow

```text
assistant-backend
  -> job-orchestrator (gRPC EnqueueJob)
  -> JetStream subject jobs.<job_type>.requested
  -> worker consume/process
```

This keeps enqueue validation and subject mapping centralized in job-orchestrator so producer services can remain transport-agnostic.

## Backwards compatibility and rollout

Use a staged cutover so deployments do not run mixed producer behavior (some instances publishing directly while others use gRPC):

1. Deploy job-orchestrator API (`EnqueueJob`) everywhere and verify gRPC readiness.
2. Roll out assistant-backend instances in waves only after orchestrator API health checks pass in the target environment.
3. Complete rollout to 100% of assistant-backend instances and confirm all new jobs are arriving via `EnqueueJob`-validated envelopes.
4. Decommission any legacy direct-producer deployment artifacts only after all environments are fully cut over.

If your deployment platform supports release flags, use them only as rollout controls (not as a long-term dual-producer mode).

## Troubleshooting

- If chat/journal integration tests fail with missing-table errors, rerun `./scripts/local/assistant-db-setup.sh`.
- In Codex containers, prefer `uv run python -m pytest` after `uv sync --extra dev` to avoid pyenv interpreter mismatch.

## Related docs

- Docs hub: [`../../docs/README.md`](../../docs/README.md)
- Local setup: [`../../docs/development/local-setup.md`](../../docs/development/local-setup.md)
- Agent runbook: [`../../docs/agents/codex-runbook.agent.md`](../../docs/agents/codex-runbook.agent.md)
- Metastore docs: [`../../infra/metastore/assistant-backend/README.md`](../../infra/metastore/assistant-backend/README.md)
