# Exobrain

Exobrain is a cloud-native AI assistant platform with a GraphRAG knowledge subsystem and living-memory architecture.

## High-level architecture

### Runtime components

- **Assistant frontend** (`apps/assistant-frontend`)
  - SvelteKit + Skeleton UI
  - Session/journal UX and client-side interaction flows
- **Assistant backend** (`apps/assistant-backend`)
  - FastAPI API + assistant domain orchestration
  - Chat, journal, auth/session, and persistence-facing services
- **Knowledge interface** (`apps/knowledge-interface`)
  - Rust tonic gRPC service
  - Retrieval/update operations for knowledge workflows
- **Metastore** (PostgreSQL)
  - Assistant state and graph metadata
- **Knowledge graph** (Memgraph)
  - Graph relationships and traversal-oriented memory state
- **Vector store** (Qdrant)
  - Embeddings/chunk indexing and semantic retrieval
- **Message broker** (NATS)
  - Async coordination across runtime services

### Deployment shape

- Kubernetes chart: `infra/helm/exobrain-stack`
- Supported development modes:
  - app-native local development
  - k3d + Helm local Kubernetes
  - Codex/cloud-agent native-process workflows

### Service/infra edit map

### Request/data flow snapshot

1. User interacts with assistant UI in `assistant-frontend`.
2. Frontend calls backend HTTP APIs in `assistant-backend`.
3. Backend coordinates domain services for chat/journal/session logic.
4. Retrieval/enrichment flows query `knowledge-interface` over gRPC.
5. Persistent state is stored in PostgreSQL, Memgraph, and Qdrant.
6. NATS supports asynchronous coordination where event-driven workflows apply.


| Change area | Primary location | Supporting locations |
| --- | --- | --- |
| Assistant API/routes/services | `apps/assistant-backend/src` | `apps/assistant-backend/tests` |
| Assistant UI/routes/stores/services | `apps/assistant-frontend/src` | `apps/assistant-frontend/tests` |
| Knowledge gRPC retrieval/update | `apps/knowledge-interface/src` | `apps/knowledge-interface/tests` |
| Kubernetes deploy wiring | `infra/helm/exobrain-stack` | `infra/docker`, `scripts/k3d` |
| Local native workflows | `scripts/local` | `docs/development/local-setup.md` |
| k3d workflows | `scripts/k3d-up.sh`, `scripts/k3d` | `docs/development/k3d-workflow.md` |
| Agent native workflows | `scripts/agent` | `docs/codex-runbook.md`, `AGENTS.md` |

## Repository map

```text
apps/
  assistant-frontend/        # SvelteKit application
  assistant-backend/         # FastAPI application
  knowledge-interface/       # Rust tonic gRPC service

docs/
  architecture-intent.md     # Long-term architecture direction
  codex-runbook.md           # Agent/cloud-environment workflow guide
  major-changes.md           # Historical incident/fix notes
  documentation-standards.md # Documentation policy and templates
  development/
    local-setup.md           # Local app-native procedural setup
    k3d-workflow.md          # k3d + Helm procedural setup

infra/
  docker/                    # Dockerfiles and build contexts
  helm/exobrain-stack/       # Kubernetes chart and values

scripts/
  local/                     # Local app + infra helper scripts
  k3d/                       # In-cluster assistant DB ops scripts
  agent/                     # Native infra scripts for agent envs
  k3d-up.sh                  # k3d bootstrap helper
```

### Directory purpose quick map

### Key subdirectory landmarks

```text
apps/assistant-backend/
  src/                       # API routers + domain services
  tests/                     # Unit/integration tests

apps/assistant-frontend/
  src/lib/components/        # Shared UI components
  src/lib/services/          # API/business orchestration
  src/lib/stores/            # Persistence/session state stores

apps/knowledge-interface/
  src/                       # gRPC server and retrieval logic
  tests/                     # Rust tests
```


- `apps/`: deployable services and their tests
- `docs/`: project-wide standards, runbooks, and workflows
- `infra/`: container + Kubernetes deployment definitions
- `scripts/`: operational helpers for local/k3d/agent workflows

## Minimal quick-start paths

Pick **one** workflow and follow the linked guide.

### Path A — Local app development (fastest iteration)

For feature implementation/debugging while infra runs locally.

- Guide: [`docs/development/local-setup.md`](docs/development/local-setup.md)
- Core scripts:
  - `./scripts/local/infra-up.sh`
  - `./scripts/local/assistant-db-setup.sh`
  - `./scripts/local/run-assistant-backend.sh`
  - `./scripts/local/run-assistant-frontend.sh`
  - `./scripts/local/run-knowledge-interface.sh`
- Typical endpoints:
  - backend: `http://localhost:8000`
  - frontend: `http://localhost:5173`
  - knowledge gRPC: `localhost:50051`

### Path B — Local Kubernetes (k3d + Helm)

For chart validation, ingress behavior, and cluster-parity checks.

- Guide: [`docs/development/k3d-workflow.md`](docs/development/k3d-workflow.md)
- Core scripts/commands:
  - `./scripts/k3d-up.sh`
  - `helm upgrade --install exobrain infra/helm/exobrain-stack --dependency-update`
  - `./scripts/k3d/assistant-db-setup.sh`
- Typical ingress endpoints:
  - frontend: `http://localhost:8080/`
  - backend: `http://localhost:8080/api`

### Path C — Codex/cloud-agent constrained environments

For environments without Docker/k3d where native services are required.

- Guide: [`docs/codex-runbook.md`](docs/codex-runbook.md)
- Core scripts:
  - `./scripts/agent/native-infra-up.sh`
  - `./scripts/agent/native-infra-health.sh`
  - `./scripts/agent/assistant-db-setup-native.sh`
  - `source .agent/state/native-infra.env`

### Minimal verification commands

### Workflow selection hints

- Choose **Path A** when changing frontend/backend business logic.
- Choose **Path B** when changing Helm values/templates, ingress, or cluster jobs.
- Choose **Path C** when working in Codex/cloud-agent containers without Docker/k3d.

### Shared prerequisites snapshot

- Docker is required for Path A infra compose and Path B k3d cluster/image flows.
- `kubectl`, Helm, and k3d are required for Path B.
- Path C relies on pre-provisioned native services and `scripts/agent/*` helpers.


Use the commands below after local setup when validating app-level changes:

```bash
cd apps/assistant-backend && uv run --with pytest --with pytest-asyncio pytest
cd apps/assistant-frontend && npm test
```

## Pointers to deeper docs

### Development and operations

- Local app-native procedures: [`docs/development/local-setup.md`](docs/development/local-setup.md)
- k3d + Helm procedures: [`docs/development/k3d-workflow.md`](docs/development/k3d-workflow.md)
- Codex/cloud-agent workflow guide: [`docs/codex-runbook.md`](docs/codex-runbook.md)

### Architecture, policy, and history

- Documentation standards and templates: [`docs/documentation-standards.md`](docs/documentation-standards.md)
- Long-term architecture direction: [`docs/architecture-intent.md`](docs/architecture-intent.md)
- Significant incident/fix history: [`docs/major-changes.md`](docs/major-changes.md)
- Agent operating constraints and conventions: [`AGENTS.md`](AGENTS.md)

### App-level reference docs

### How to choose the right doc quickly

- Need exact startup/build/run commands: use development workflow docs.
- Need policy about doc structure/content: use documentation standards.
- Need historical regression context: use major-changes timeline.
- Need constraints for automated agents: use `AGENTS.md`.


- Backend details: [`apps/assistant-backend/README.md`](apps/assistant-backend/README.md)
- Frontend details: [`apps/assistant-frontend/README.md`](apps/assistant-frontend/README.md)
- Knowledge interface details: [`apps/knowledge-interface/README.md`](apps/knowledge-interface/README.md)
