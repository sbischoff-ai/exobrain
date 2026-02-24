# Local Development Setup

## Why this exists

This guide documents the procedural local workflow for running Exobrain apps directly on your machine while using local infrastructure services.

## Scope

Use this path for fast iteration during feature development and debugging.

## Prerequisites

- Docker (for local infra compose stack)
- Python + `uv` (assistant backend)
- Node/npm (assistant frontend)
- Rust/Cargo (knowledge interface)

Environment variables (set in the shell where scripts are run):

- `OPENAI_API_KEY` (required only when backend uses real model)
- `MAIN_AGENT_USE_MOCK=true|false` (optional; defaults vary by script/environment)
- `MAIN_AGENT_MOCK_MESSAGES_FILE=mock-data/main-agent-messages.md` (optional mock response source)

## Workflow

### 1) Start local infrastructure

```bash
./scripts/local/infra-up.sh
```

This starts:

- PostgreSQL on `localhost:15432`
- Qdrant on `localhost:16333` (HTTP), `localhost:16334` (gRPC)
- Memgraph on `localhost:17687` (Bolt), `localhost:17444` (HTTP)
- NATS on `localhost:14222` (client), `localhost:18222` (monitoring)

### 2) Initialize assistant database

```bash
./scripts/local/assistant-db-migrate.sh
```

Optional seed data:

```bash
./scripts/local/assistant-db-seed.sh
```

Reset and reseed test data:

```bash
./scripts/local/assistant-db-reset-and-seed.sh
```

Or run both in order:

```bash
./scripts/local/assistant-db-setup.sh
./scripts/local/job-orchestrator-db-setup.sh
```

### 3) Build applications

```bash
./scripts/local/build-assistant-backend.sh
./scripts/local/build-assistant-frontend.sh
./scripts/local/build-knowledge-interface.sh
./scripts/local/build-job-orchestrator.sh
```

Build notes:

- Frontend build script runs `npm ci` when dependencies are missing/stale, then `npm run build`.
- Backend build script runs `uv sync` and compiles changed Python bytecode.
- Knowledge interface build script runs `cargo build`.

### 4) Run services (separate terminals)

For knowledge-interface local config:

```bash
cp apps/knowledge-interface/.env.example apps/knowledge-interface/.env
# set OPENAI_API_KEY in your shell
```

Then run:

```bash
./scripts/local/run-assistant-backend.sh
./scripts/local/run-assistant-frontend.sh
./scripts/local/run-knowledge-interface.sh
./scripts/local/run-job-orchestrator.sh
```

Apply knowledge schema migrations:

```bash
./scripts/local/knowledge-schema-migrate.sh
```

Optional: seed starter graph schema types:

```bash
./scripts/local/knowledge-schema-seed.sh
```

Default local app endpoints:

- Backend API: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- Knowledge interface gRPC: `localhost:50051`
- Job orchestrator worker: subscribes on NATS `jobs.>`

When `APP_ENV=local`, knowledge-interface enables gRPC reflection so you can inspect APIs with `grpcui`.

Use plaintext mode locally:

```bash
grpcui -plaintext localhost:50051
```

If you see `tls: first record does not look like a TLS handshake`, grpcui was run without `-plaintext`.

### 5) Run unit tests

```bash
cd apps/assistant-backend && uv run --with pytest --with pytest-asyncio pytest
cd apps/assistant-frontend && npm test
```

Notes:

- Backend unit tests are designed to run without live infra.
- Frontend tests run via Vitest + JSDOM.

### 6) Stop infrastructure

```bash
./scripts/local/infra-down.sh
```

## References

- Root index: [`README.md`](../../README.md)
- k3d/Helm workflow: [`k3d-workflow.md`](k3d-workflow.md)
- Codex/cloud-agent runbook: [`../agents/codex-runbook.agent.md`](../agents/codex-runbook.agent.md)
