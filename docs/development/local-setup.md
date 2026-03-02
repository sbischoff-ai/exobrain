# Local Development Setup

## Why this exists

This guide is the canonical local setup path for development on your workstation.

## Scope

Use this path for fast feature iteration with Docker Compose for infra and `mprocs` for Exobrain application processes.

## Prerequisites

- Docker (for local infra compose stack)
- `mprocs` (process orchestration for Exobrain services)
- Python + `uv` (assistant backend, job orchestrator)
- Node/npm (assistant frontend)
- Rust/Cargo (knowledge interface)

`mprocs` is provided by `shell.nix`.

## Pick a run profile

| Goal                            | Profile             | App launcher                                                                       |
| ------------------------------- | ------------------- | ---------------------------------------------------------------------------------- |
| Backend APIs + jobs only        | Backend             | `./scripts/local/run-backend-suite.sh` (default config)                            |
| Backend APIs + knowledge + jobs | Backend + knowledge | `MPROCS_CONFIG=.mprocs/backend-knowledge.yml ./scripts/local/run-backend-suite.sh` |
| Full stack (includes frontend)  | Full stack          | `./scripts/local/run-fullstack-suite.sh`                                           |

## Workflow

### 1) Start infrastructure (Docker Compose)

```bash
./scripts/local/infra-up.sh
```

This starts PostgreSQL, Redis, NATS, Qdrant, Memgraph, and Memgraph Lab.

### 2) Apply required schema setup

```bash
./scripts/local/assistant-db-setup.sh
./scripts/local/job-orchestrator-db-setup.sh
./scripts/local/knowledge-schema-setup.sh
# optional full reset helpers:
./scripts/local/knowledge-schema-reset-and-seed.sh
./scripts/local/knowledge-graph-reset.sh
```

`knowledge-graph-reset.sh` preserves prior running state for memgraph/qdrant/memgraph-lab (does not auto-start if they were down).

### 3) Build applications (when dependencies or source changed)

```bash
./scripts/local/build-assistant-backend.sh
./scripts/local/build-job-orchestrator.sh
./scripts/local/build-knowledge-interface.sh
./scripts/local/build-assistant-frontend.sh
```

### 4) Start app processes with mprocs

Startup dependency note: start `job-orchestrator` alongside `assistant-backend` before validating `/api/knowledge/update`, because assistant-backend now enqueues work through orchestrator `EnqueueJob` gRPC instead of publishing directly to NATS.

Backend + knowledge profile:

```bash
MPROCS_CONFIG=.mprocs/backend-knowledge.yml ./scripts/local/run-backend-suite.sh
```

Full-stack profile:

```bash
./scripts/local/run-fullstack-suite.sh
```

Knowledge-update enqueue flow:

```text
assistant-backend -> job-orchestrator (gRPC EnqueueJob) -> JetStream jobs.<job_type>.requested -> worker consume/process
```

### 5) Verify and run tests

```bash
cd apps/assistant-backend && uv run --with pytest --with pytest-asyncio pytest
cd apps/assistant-frontend && npm test
```

Default local endpoints:

- Backend API: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- Knowledge interface gRPC: `localhost:50051`
- Memgraph Lab UI: `http://localhost:13000`
- Qdrant dashboard: `http://localhost:16333/dashboard`

### 6) Stop everything

- Stop mprocs by pressing `Ctrl+C` in the mprocs terminal.
- Stop infra services:

```bash
./scripts/local/infra-down.sh
```

## References

- Process orchestration guide: [`process-orchestration.md`](./process-orchestration.md)
- Root index: [`../../README.md`](../../README.md)
- k3d/Helm workflow: [`k3d-workflow.md`](./k3d-workflow.md)
- Codex/cloud-agent runbook: [`../agents/codex-runbook.agent.md`](../agents/codex-runbook.agent.md)
