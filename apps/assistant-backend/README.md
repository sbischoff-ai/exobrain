# Exobrain Assistant Backend

FastAPI service for chat orchestration and GraphRAG context augmentation.

## Architecture overview

The backend now follows a small but extensible layered design:

- **API layer** (`app/api`): request schemas and HTTP routers.
- **Service layer** (`app/services`): use-case orchestration, independent from FastAPI.
- **Agent layer** (`app/agents`): chat agent interfaces and implementations.
- **Core layer** (`app/core`): runtime configuration and app settings.

The current implementation ships one main assistant agent backed by LangChain `ChatOpenAI`
using model `gpt-5.2` with streaming enabled. It also supports a file-driven mock model
for offline development/testing.

## Environment configuration

Create a local env file from the example:

```bash
cp .env.example .env
```

`OPENAI_API_KEY` is intentionally **not** stored in `.env` and must be provided externally when using the real OpenAI-backed model. (Set it in the terminal session that's running the backend process.)

Model selection settings:

- `MAIN_AGENT_USE_MOCK=false` (default): use real OpenAI model (`MAIN_AGENT_MODEL`, `MAIN_AGENT_TEMPERATURE`).
- `MAIN_AGENT_USE_MOCK=true`: use file-driven mock model and ignore prompt content.
- `MAIN_AGENT_MOCK_MESSAGES_FILE=mock-data/main-agent-messages.md`: markdown file containing responses separated by the delimiter `\n--- message\n`.

The mock model cycles through configured responses and wraps back to the first message after the last one.

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
- `POST /api/chat/message` accepts optional auth via cookie or bearer token and logs the resolved user name.

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
uv run --with pytest --with pytest-asyncio pytest -m "not integration"
```

This runs the backend unit suite (service/auth/dependency behavior) without requiring live infrastructure services.

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

For coding agents in Codex/cloud environments, use this flow:

```bash
./scripts/agent/native-infra-up.sh
./scripts/agent/assistant-db-setup-native.sh
source .agent/state/native-infra.env
export MAIN_AGENT_USE_MOCK=true
./scripts/local/run-assistant-backend.sh

cd apps/assistant-backend
cp tests/integration/.env.integration.example tests/integration/.env.integration
uv run --with pytest --with pytest-asyncio --with httpx pytest -m integration
```

## Local environment endpoints

### Application endpoint

- Assistant backend API: `http://localhost:8000/api`
- Health check: `http://localhost:8000/healthz`
- Auth login endpoint: `POST http://localhost:8000/api/auth/login`
- Chat endpoint: `POST http://localhost:8000/api/chat/message`
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
