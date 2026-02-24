# Exobrain

Exobrain is a cloud-native AI assistant platform with a GraphRAG-oriented knowledge subsystem and living-memory architecture.

## What this repository contains

- **Assistant frontend** (`apps/assistant-frontend`): SvelteKit UI for authentication, journal navigation, and chat flows.
- **Assistant backend** (`apps/assistant-backend`): FastAPI service for auth, chat orchestration, and journal/message APIs.
- **Knowledge interface** (`apps/knowledge-interface`): Rust tonic gRPC service for retrieval and knowledge updates.
- **Job orchestrator** (`apps/job-orchestrator`): Python worker service for NATS-backed asynchronous jobs.
- **Infrastructure** (`infra/`): Docker images, Helm chart, and metastore migration/seed assets.
- **Operational scripts** (`scripts/`): local app-native, k3d, and agent-native workflow helpers.

## Quick start workflows

Choose one startup path and use its canonical runbook.

| Goal | Infra runtime | App process runtime | Primary guide |
| --- | --- | --- | --- |
| Fast local app iteration | Docker Compose | `mprocs` | [`docs/development/local-setup.md`](docs/development/local-setup.md) |
| Helm/ingress/cluster validation | k3d + Helm | Kubernetes workloads | [`docs/development/k3d-workflow.md`](docs/development/k3d-workflow.md) |
| Codex/cloud-agent constrained environments | Native local services | native scripts | [`docs/agents/codex-runbook.agent.md`](docs/agents/codex-runbook.agent.md) |

## Repository map

```text
apps/
  assistant-frontend/
  assistant-backend/
  knowledge-interface/
  job-orchestrator/

docs/
  README.md
  architecture/
  development/
  standards/
  operations/
  agents/

infra/
  docker/
  helm/exobrain-stack/
  metastore/

scripts/
  local/
  k3d/
  agent/
```

## Common validation commands

```bash
cd apps/assistant-backend && uv run --with pytest --with pytest-asyncio pytest
cd apps/assistant-frontend && npm test
```

## Documentation index

- Documentation hub: [`docs/README.md`](docs/README.md)
- Architecture overview: [`docs/architecture/architecture-overview.md`](docs/architecture/architecture-overview.md)
- Architecture intent: [`docs/architecture/architecture-intent.md`](docs/architecture/architecture-intent.md)
- Development workflows:
  - local app-native: [`docs/development/local-setup.md`](docs/development/local-setup.md)
  - local process orchestration: [`docs/development/process-orchestration.md`](docs/development/process-orchestration.md)
  - k3d + Helm: [`docs/development/k3d-workflow.md`](docs/development/k3d-workflow.md)
  - codex/cloud-agent: [`docs/agents/codex-runbook.agent.md`](docs/agents/codex-runbook.agent.md)
- Standards:
  - documentation policy: [`docs/standards/documentation-standards.md`](docs/standards/documentation-standards.md)
  - engineering standards: [`docs/standards/engineering-standards.md`](docs/standards/engineering-standards.md)
- Operations history: [`docs/operations/major-changes.md`](docs/operations/major-changes.md)

## Service-level READMEs

- Backend: [`apps/assistant-backend/README.md`](apps/assistant-backend/README.md)
- Frontend: [`apps/assistant-frontend/README.md`](apps/assistant-frontend/README.md)
- Knowledge interface: [`apps/knowledge-interface/README.md`](apps/knowledge-interface/README.md)
- Job orchestrator: [`apps/job-orchestrator/README.md`](apps/job-orchestrator/README.md)
