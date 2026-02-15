# Exobrain

Exobrain is a cloud-native scaffold for an AI chat assistant with a GraphRAG knowledge base and living-memory architecture.

## Architecture

This repository includes scaffolding for the following components:

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
```

## Prerequisites

- Docker
- `kubectl`
- Helm 3
- k3d

## Local Development (k3d)

### 1. Create a local cluster

```bash
./scripts/k3d-up.sh
```

Sane local defaults:
- 1 server + 2 agents
- Traefik disabled (so ingress choice stays explicit)
- LoadBalancer ports mapped: `8080 -> 80`, `8443 -> 443`

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
helm upgrade --install exobrain infra/helm/exobrain-stack
```

### 4. Inspect deployment

```bash
kubectl get pods
kubectl get svc
```

## Configuration

The chart is fully parameterized via `infra/helm/exobrain-stack/values.yaml`, including:

- Replica counts for each service.
- Container image repositories/tags.
- CPU/memory requests + limits.
- Persistent volume sizes and optional storage class.
- Service ports and optional ingress.

For local tuning, create a `values.local.yaml` override file and apply with:

```bash
helm upgrade --install exobrain infra/helm/exobrain-stack -f values.local.yaml
```

## Notes

- This is intentionally minimal scaffolding with startup-ready services, not full application functionality.
- For production, add:
  - Secret management (e.g., external secrets / sealed secrets)
  - Pod security context and network policies
  - TLS and ingress controller
  - Observability stack (metrics, logs, tracing)
  - HorizontalPodAutoscaler and disruption budgets
