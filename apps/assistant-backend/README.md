# Exobrain Assistant Backend

FastAPI service for chat orchestration and GraphRAG context augmentation.

## Architecture overview

The backend now follows a small but extensible layered design:

- **API layer** (`app/api`): request schemas and HTTP routers.
- **Service layer** (`app/services`): use-case orchestration, independent from FastAPI.
- **Agent layer** (`app/agents`): chat agent interfaces and implementations.
- **Core layer** (`app/core`): runtime configuration and app settings.

The current implementation ships one main assistant agent backed by LangChain `ChatOpenAI`
using model `gpt-5.2` with streaming enabled.

## Environment configuration

Create a local env file from the example:

```bash
cp .env.example .env
```

`OPENAI_API_KEY` is intentionally **not** stored in `.env` and must be provided externally. (Set it in the terminal session that's running the backend process.)

Swagger/OpenAPI is environment-gated:

- `APP_ENV=local` -> Swagger UI is enabled (`/docs`).
- any non-local value (for example in Kubernetes) -> Swagger/OpenAPI is disabled.

## Local build and run

From the repository root:

```bash
./scripts/local/build-assistant-backend.sh
./scripts/local/run-assistant-backend.sh
```

Notes:
- The build script keeps `.venv` in sync via `uv sync` and only updates dependencies when needed.
- Python is interpreted at runtime; rebuild is mainly needed when dependencies or packaging metadata change.

## Local environment endpoints

### Application endpoint

- Assistant backend API: `http://localhost:8000/api`
- Health check: `http://localhost:8000/healthz`
- Chat endpoint: `POST http://localhost:8000/api/chat/message`
- Swagger UI (local only): `http://localhost:8000/docs`

### Infrastructure dependencies (default script wiring)

- PostgreSQL: `localhost:15432`
- Qdrant: `localhost:16333` (HTTP), `localhost:16334` (gRPC)
- Memgraph: `localhost:17687` (Bolt), `localhost:17444` (HTTP)
- NATS: `localhost:14222` (client), `localhost:18222` (monitoring)

## Kubernetes baseline

The project local cluster helper (`scripts/k3d-up.sh`) defaults to:

- Kubernetes image: `rancher/k3s:v1.35.1-k3s1`
- Local LoadBalancer mapping: `localhost:8080 -> :80`, `localhost:8443 -> :443`
- Ingress routing: `http://localhost:8080/` -> assistant frontend, `http://localhost:8080/api` -> assistant backend
