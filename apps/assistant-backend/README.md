# Exobrain Assistant Backend

FastAPI service for chat orchestration and GraphRAG context augmentation.

## Architecture overview

The backend follows a layered design:

- **API layer** (`app/api`): request schemas and HTTP routers.
- **Service layer** (`app/services`): use-case orchestration, independent from FastAPI.
- **Agent layer** (`app/agents`): chat agent interfaces and implementations.
- **Core layer** (`app/core`): runtime configuration and app settings.

Cross-service standards for router/service boundaries are documented in [`docs/standards/engineering-standards.md`](../../docs/standards/engineering-standards.md).

The current implementation uses LangChain `create_agent()` with LangGraph streaming and a
Postgres-backed checkpointer so each journal conversation has isolated memory by conversation id.
It supports either `ChatOpenAI` (default) or `FakeListChatModel` for offline development/testing.

Agent tools are defined under `app/agents/tools` and wrapped behind stable tool contracts. The
main assistant now includes `web_search` (source discovery) and `web_fetch` (plaintext fetch)
implemented via `langchain-tavily`.

## Environment configuration

Create a local env file from the example:

```bash
cp .env.example .env
```

`OPENAI_API_KEY` is intentionally **not** stored in `.env` and must be provided externally when using the real OpenAI-backed model. (Set it in the terminal session that's running the backend process.)
`TAVILY_API_KEY` follows the same pattern for web-search/web-fetch tools.

Model selection settings:

- `MAIN_AGENT_USE_MOCK=false` (default): use real OpenAI model (`MAIN_AGENT_MODEL`, `MAIN_AGENT_TEMPERATURE`).
- `MAIN_AGENT_USE_MOCK=true`: use `FakeListChatModel` responses loaded from markdown.
- `MAIN_AGENT_MOCK_MESSAGES_FILE=mock-data/main-agent-messages.md`: markdown file containing responses separated by `\n\n--- message ---\n\n`.
- `MAIN_AGENT_SYSTEM_PROMPT=...`: optional system prompt override for assistant behavior.
- `TAVILY_API_KEY=...`: optional key for web tools (`web_search`, `web_fetch`) when real model mode is active.
- `WEB_TOOLS_USE_MOCK=false` (default): set to `true` to avoid Tavily network calls and return offline mock tool payloads.
- `WEB_TOOLS_MOCK_DATA_FILE=mock-data/web-tools.mock.json`: optional JSON file overriding mock `web_search` and `web_fetch` payloads.

The fake model cycles through configured responses and wraps back to the first message after the last one.

Session storage settings:

- `ASSISTANT_CACHE_REDIS_URL=redis://localhost:16379/0`: Redis URL for auth sessions.
- `ASSISTANT_CACHE_KEY_PREFIX=assistant:sessions`: key namespace used for session records.

Swagger/OpenAPI is environment-gated:

- `APP_ENV=local` -> Swagger UI is enabled (`/docs`).
- any non-local value (for example in Kubernetes) -> Swagger/OpenAPI is disabled.

Logging behavior:

- `LOG_LEVEL` can override runtime logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
- If `LOG_LEVEL` is unset, backend defaults to `DEBUG` in `APP_ENV=local` and `INFO` otherwise.
- Structured, security-conscious logs avoid token/session payload dumps while still emitting auth/chat lifecycle events.


## Database and auth setup

Assistant backend now uses a dedicated Postgres database (`assistant_db`) and user (`assistant_backend`).

Apply database bootstrap, Reshape migrations, and seed data locally:

```bash
./scripts/local/assistant-db-setup.sh
```

This applies TOML-based Reshape migrations from `infra/metastore/assistant-backend/migrations/`, then inserts a test user:

- email: `test.user@exobrain.local`
- password: `password123`

## Authentication

- `POST /api/auth/login` authenticates a user and can issue:
  - session cookie mode (`session_mode=web`, `issuance_policy=session`)
  - token pair mode (`session_mode=api`, `issuance_policy=tokens`)
- `POST /api/auth/token_refresh` accepts an API refresh token and returns a rotated access+refresh pair.
- `POST /api/chat/message` now requires authentication and a `client_message_id` UUID for idempotency. It responds with a `stream_id` and persists user/assistant journal messages around the asynchronous stream processing lifecycle
- `GET /api/chat/stream/{stream_id}` serves an SSE stream (`text/event-stream`) with `message_chunk`, `tool_call`, `tool_response`, and `error` events for the pending assistant reply
- Journal APIs (`/api/journal`, `/api/journal/today`, `/api/journal/{reference}`, `/api/journal/{reference}/messages`, `/api/journal/search`) provide authenticated access to persisted conversation history.
- Message endpoints paginate with a `sequence` cursor and return newest-first results by default.

## Local build and run

From the repository root:

```bash
./scripts/local/build-assistant-backend.sh
./scripts/local/run-assistant-backend.sh
```

Notes:
- The build script keeps `.venv` in sync via `uv sync` and only updates dependencies when needed.
- Python is interpreted at runtime; rebuild is mainly needed when dependencies or packaging metadata change.


## Running unit tests

From `apps/assistant-backend` run:

```bash
uv sync --extra dev
uv run python -m pytest -m "not integration"
```

This runs the backend unit suite (service/auth/dependency behavior) without requiring live infrastructure services.

> Why this exact flow? In some Codex environments, `python3`/`pytest` on `PATH` can resolve to a pyenv-managed Python 3.10 shim. Syncing dev dependencies and invoking `pytest` via `uv run python -m pytest` ensures the project `.venv` interpreter (Python 3.12 here) is used consistently.

## Running integration tests

Integration tests are intentionally separate and target a running backend URL configured in an env file.

1. Create integration env config:

```bash
cp tests/integration/.env.integration.example tests/integration/.env.integration
```

2. Set `ASSISTANT_BACKEND_BASE_URL` in that file. Examples:
   - local backend process: `http://localhost:8000`
   - k3d ingress: `http://localhost:8080`

3. Run integration tests:

```bash
ASSISTANT_BACKEND_INTEGRATION_ENV_FILE=tests/integration/.env.integration \
  uv run --with pytest --with pytest-asyncio --with httpx pytest -m integration
```

The suite expects seeded auth user data to exist on the target backend:

- email: `test.user@exobrain.local`
- password: `password123`

If chat/journal integration tests fail with missing-table errors, re-run database setup (`./scripts/agent/assistant-db-setup-native.sh` or `./scripts/local/assistant-db-setup.sh`) so Reshape migrations are fully applied before starting the backend.

For coding agents in Codex/cloud environments, use this flow:

```bash
./scripts/agent/assistant-offline-up.sh
./scripts/agent/run-assistant-backend-offline.sh

cd apps/assistant-backend
cp tests/integration/.env.integration.example tests/integration/.env.integration
uv run --with pytest --with pytest-asyncio --with httpx pytest -m integration
```

`run-assistant-backend-offline.sh` defaults both `MAIN_AGENT_USE_MOCK=true` and `WEB_TOOLS_USE_MOCK=true`, so chat works without OpenAI or Tavily access.

## Local environment endpoints

### Application endpoint

- Assistant backend API: `http://localhost:8000/api`
- Health check: `http://localhost:8000/healthz`
- Auth login endpoint: `POST http://localhost:8000/api/auth/login`
- Chat endpoint: `POST http://localhost:8000/api/chat/message` (authenticated; include `client_message_id`)
- Token refresh endpoint: `POST http://localhost:8000/api/auth/token_refresh`
- Journal endpoints: `GET http://localhost:8000/api/journal*`
- Swagger UI (local only): `http://localhost:8000/docs`

### Infrastructure dependencies (default script wiring)

- PostgreSQL: `localhost:15432`
- Qdrant: `localhost:16333` (HTTP), `localhost:16334` (gRPC)
- Memgraph: `localhost:17687` (Bolt), `localhost:17444` (HTTP)
- NATS: `localhost:14222` (client), `localhost:18222` (monitoring)
- Redis (assistant-cache): `localhost:16379`

## Kubernetes baseline

The project local cluster helper (`scripts/k3d-up.sh`) defaults to:

- Kubernetes image: `rancher/k3s:v1.35.1-k3s1`
- Local LoadBalancer mapping: `localhost:8080 -> :80`, `localhost:8443 -> :443`
- Ingress routing: `http://localhost:8080/` -> assistant frontend, `http://localhost:8080/api` -> assistant backend


## Related docs

- Repository docs hub: [`../../docs/README.md`](../../docs/README.md)
- Local setup workflow: [`../../docs/development/local-setup.md`](../../docs/development/local-setup.md)
- Engineering standards: [`../../docs/standards/engineering-standards.md`](../../docs/standards/engineering-standards.md)
- Architecture overview: [`../../docs/architecture/architecture-overview.md`](../../docs/architecture/architecture-overview.md)
