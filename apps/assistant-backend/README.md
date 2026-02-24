# Exobrain Assistant Backend

FastAPI service for auth, chat orchestration, journal APIs, and async job publishing.

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

## Configuration

Core runtime vars:

- `ASSISTANT_DB_DSN` (Postgres metastore)
- `ASSISTANT_CACHE_REDIS_URL` (session store)
- `EXOBRAIN_NATS_URL` (job publishing)
- `EXOBRAIN_QDRANT_URL`, `EXOBRAIN_MEMGRAPH_URL` (knowledge dependencies)
- `RESHAPE_SCHEMA_QUERY` (migration introspection)

Model/tool vars:

- `MAIN_AGENT_USE_MOCK=true|false`
- `MAIN_AGENT_MOCK_MESSAGES_FILE`
- `OPENAI_API_KEY` (required for real model)
- `TAVILY_API_KEY` (required for real web tools)
- `WEB_TOOLS_USE_MOCK=true|false`

OpenAPI and logging:

- `APP_ENV=local` enables `/docs`; non-local disables OpenAPI docs.
- `LOG_LEVEL` overrides defaults (`DEBUG` local, `INFO` otherwise).

## Troubleshooting

- If chat/journal integration tests fail with missing-table errors, rerun `./scripts/local/assistant-db-setup.sh`.
- In Codex containers, prefer `uv run python -m pytest` after `uv sync --extra dev` to avoid pyenv interpreter mismatch.

## Related docs

- Docs hub: [`../../docs/README.md`](../../docs/README.md)
- Local setup: [`../../docs/development/local-setup.md`](../../docs/development/local-setup.md)
- Agent runbook: [`../../docs/agents/codex-runbook.agent.md`](../../docs/agents/codex-runbook.agent.md)
- Metastore docs: [`../../infra/metastore/assistant-backend/README.md`](../../infra/metastore/assistant-backend/README.md)
