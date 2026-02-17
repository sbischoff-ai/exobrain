# Exobrain

Exobrain is a cloud-native system for an AI chat assistant with a GraphRAG knowledge base and living-memory architecture.

## Architecture

This repository includes the foundational services for the following components:

- **Exobrain Assistant Frontend** (`apps/assistant-frontend`): SvelteKit + Skeleton chatbot UI.
- **Exobrain Assistant Backend** (`apps/assistant-backend`): FastAPI + LangChain orchestration API.
- **Exobrain Metastore**: PostgreSQL for assistant state + graph schema metadata.
- **Exobrain Knowledge Interface** (`apps/knowledge-interface`): Rust gRPC service for GraphRAG retrieval + updates.
- **Exobrain Knowledge Graph**: Memgraph for graph storage.
- **Exobrain Vector Store**: Qdrant for chunks/embeddings.
- **Exobrain Message Broker**: NATS for async coordination.

Helm chart path: `infra/helm/exobrain-stack`.

## Repository Layout

```text
apps/
  assistant-frontend/        # SvelteKit app
  assistant-backend/         # FastAPI app
  knowledge-interface/       # Rust tonic gRPC service
infra/
  docker/                    # Dockerfiles for all components
  helm/exobrain-stack/       # Kubernetes Helm chart
scripts/
  k3d-up.sh                  # local cluster bootstrap helper
  local/                     # scripts for local service and infrastructure startup
```

## Prerequisites

- Docker
- `kubectl`
- Helm 3
- k3d

Optional (for NixOS):
- Nix with flakes or classic `nix-shell`

Environment Variables:
- `OPENAI_API_KEY` (for Assistant backend)

(Env vars need to be present in the terminal that you execute scripts like `run-assistant-backend.sh` or `k3d-up.sh` in.)

## Local Environment Overview

### Kubernetes baseline

- k3d cluster script default image: `rancher/k3s:v1.35.1-k3s1`
- LoadBalancer ports mapped locally: `8080 -> 80`, `8443 -> 443`

### Local infrastructure compose endpoints

Run `./scripts/local/infra-up.sh` to start these infrastructure services:

- PostgreSQL: `localhost:15432` (`postgresql://exobrain:exobrain@localhost:15432/exobrain`)
- Qdrant: `localhost:16333` (HTTP), `localhost:16334` (gRPC)
- Memgraph: `localhost:17687` (Bolt), `localhost:17444` (HTTP)
- NATS: `localhost:14222` (client), `localhost:18222` (monitoring)

### Local app endpoints (when running app scripts)

- Assistant backend API: `http://localhost:8000`
- Assistant frontend app: `http://localhost:5173`
- Knowledge interface gRPC: `localhost:50051`

## Local Development (k3d)

### 1. Create a local cluster

```bash
./scripts/k3d-up.sh
```

Sane local defaults:
- 1 server + 2 agents
- Traefik enabled (default k3s ingress controller)
- LoadBalancer ports mapped: `8080 -> 80`, `8443 -> 443`
- Kubernetes image: `rancher/k3s:v1.35.1-k3s1`

### 2. Build local images (optional for custom services)

```bash
docker build -f infra/docker/assistant-frontend/Dockerfile -t exobrain/assistant-frontend:0.1.0 .
docker build -f infra/docker/assistant-backend/Dockerfile -t exobrain/assistant-backend:0.1.0 .
docker build -f infra/docker/knowledge-interface/Dockerfile -t exobrain/knowledge-interface:0.1.0 .
```

Import images into k3d cluster:

```bash
k3d image import \
  exobrain/assistant-frontend:0.1.0 \
  exobrain/assistant-backend:0.1.0 \
  exobrain/knowledge-interface:0.1.0 \
  -c exobrain-dev
```

### 3. Deploy Helm chart

```bash
helm upgrade --install exobrain infra/helm/exobrain-stack --dependency-update
```

### 4. Inspect deployment

```bash
kubectl get pods
kubectl get svc
```

### 5. Access assistant services via ingress

Once the chart is deployed, both assistant services are reachable via the same local port:

- Assistant frontend: `http://localhost:8080/`
- Assistant backend API: `http://localhost:8080/api`

Ingress routing is path-based (`/api` -> assistant backend, all other paths -> assistant frontend).

## Local App Development (without full Kubernetes rollout)

For iterative debugging, you can run the app services directly in your terminal while keeping only infrastructure services in Docker Compose.

### 1. Start local infrastructure services

```bash
./scripts/local/infra-up.sh
```

This starts:
- PostgreSQL on `localhost:15432`
- Qdrant on `localhost:16333` (HTTP) and `localhost:16334` (gRPC)
- Memgraph on `localhost:17687` (Bolt) and `localhost:17444` (HTTP)
- NATS on `localhost:14222` (client) and `localhost:18222` (monitoring)

### 2. Build local apps

Before running services, build each app once from a fresh clone (and re-run when noted below):

```bash
./scripts/local/build-assistant-backend.sh
./scripts/local/build-assistant-frontend.sh
./scripts/local/build-knowledge-interface.sh
```

Build script behavior:
- Frontend: installs dependencies with `npm ci` only when needed (missing `node_modules` or lockfile change), then runs `npm run build`.
- Backend: runs `uv sync` (dependency-aware, no-op when up to date) and compiles Python bytecode for changed files.
- Knowledge interface: runs `cargo build --locked`; Cargo rebuilds only changed crates/files.

### 3. Run services directly

In separate terminals:

```bash
./scripts/local/run-assistant-backend.sh
./scripts/local/run-assistant-frontend.sh
./scripts/local/run-knowledge-interface.sh
```

All scripts expose placeholder connection environment variables for Postgres, Qdrant, Memgraph, and NATS so local services can share a consistent default topology.

### 4. Stop local infrastructure services

```bash
./scripts/local/infra-down.sh
```

## NixOS Development Shell

For NixOS users, `shell.nix` provides a ready-to-use environment for:
- k3d/Helm/kubectl workflows
- Python + `uv` backend development
- Node/Svelte frontend development
- Rust/Cargo knowledge-interface builds
- datastore CLIs (`psql`, `cypher-shell`, `curl`/`http`)

Enter it with:

```bash
nix-shell
```

## Configuration

The chart is fully parameterized via `infra/helm/exobrain-stack/values.yaml`, including:

- Replica counts for each service.
- Container image repositories/tags.
- CPU/memory requests + limits.
- Persistent volume sizes and optional storage class.
- Service ports and ingress routing (frontend on `/`, backend on `/api`).

For local tuning, create a `values.local.yaml` override file and apply with:

```bash
helm upgrade --install exobrain infra/helm/exobrain-stack -f values.local.yaml
```

## Notes

- The repository currently provides infrastructure and service wiring with minimal application logic; functional features can be implemented incrementally on top.
- For production, add:
  - Secret management (e.g., external secrets / sealed secrets)
  - Pod security context and network policies
  - TLS and ingress controller
  - Observability stack (metrics, logs, tracing)
  - HorizontalPodAutoscaler and disruption budgets
