# Exobrain Assistant Backend

FastAPI service for auth, chat orchestration, journal APIs, and knowledge-base update workflows. Includes `/api/knowledge/update` to update the knowledge base from journal messages via job-orchestrator gRPC enqueue (not direct NATS publish).

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

## Seed Memgraph test data for assistant-backend

Use the canned knowledge-interface gRPC payloads to initialize graph state for the seeded assistant-backend test user (`test.user@exobrain.local`) and upsert a realistic task + block tree for GraphRAG testing.

```bash
./scripts/local/add-assistant-backend-memgraph-test-data.sh
```

The script reads:

- `apps/assistant-backend/mock-data/knowledge/initialize-user-graph.request.json`
- `apps/assistant-backend/mock-data/knowledge/upsert-graph-delta.request.template.json`

Optional overrides:

- `KNOWLEDGE_GRPC_TARGET` (default `127.0.0.1:50051`)
- `INIT_REQUEST_PATH`
- `DELTA_TEMPLATE_PATH`

## Configuration

Core runtime vars:

- `ASSISTANT_DB_DSN` (Postgres metastore)
- `ASSISTANT_CACHE_REDIS_URL` (session store)
- `JOB_ORCHESTRATOR_GRPC_TARGET` (required orchestrator `EnqueueJob` gRPC endpoint, default `localhost:50061`)
- Knowledge update requests do **not** publish to NATS directly from assistant-backend. The backend calls orchestrator `EnqueueJob` with `user_id`, `job_type=knowledge.update`, and a typed payload containing `journal_reference`, message entries, and `requested_by_user_id`.
- `JOB_ORCHESTRATOR_CONNECT_TIMEOUT_SECONDS` (gRPC request timeout in seconds, default `5.0`)
- `EXOBRAIN_QDRANT_URL`, `EXOBRAIN_MEMGRAPH_URL` (knowledge dependencies)
- `KNOWLEDGE_UPDATE_MAX_TOKENS` (max tokens per knowledge-update job payload, default `8000`)
- `RESHAPE_SCHEMA_QUERY` (migration introspection)

Model/tool vars:

- Main agent prompt includes markdown rendering guidance for math and diagrams (`$...$`, `$$...$$`, and ```mermaid fenced blocks; display math is expected on its own lines).
- `MAIN_AGENT_USE_MOCK=true|false`
- `MAIN_AGENT_MOCK_MESSAGES_FILE`
- `MODEL_PROVIDER_BASE_URL` (default `http://localhost:8010/v1`)
- `MAIN_AGENT_MODEL` (alias, default `agent`)
- `TAVILY_API_KEY` (required for real web tools)
- `WEB_TOOLS_USE_MOCK=true|false`

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
