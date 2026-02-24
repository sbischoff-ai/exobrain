# k3d + Helm Local Workflow

## Why this exists

This guide documents the procedural Kubernetes-first local workflow for Exobrain using k3d and Helm.

## Scope

Use this path when validating in-cluster behavior, chart changes, ingress routing, and hook jobs.

## Prerequisites

- Docker
- `kubectl`
- Helm 3
- k3d

Optional (NixOS): use `nix-shell` from repository root.

## Workflow

### 1) Create the local cluster

```bash
./scripts/k3d-up.sh
```

Default behavior includes:

- k3s image: `rancher/k3s:v1.35.1-k3s1`
- 1 server + 2 agents
- Traefik ingress enabled
- Local LB mappings: `8080 -> 80`, `8443 -> 443`

### 2) Build local images (optional)

Use when iterating on local container image changes.

```bash
docker build -f infra/docker/assistant-frontend/Dockerfile -t exobrain/assistant-frontend:0.1.0 .
docker build -f infra/docker/assistant-backend/Dockerfile -t exobrain/assistant-backend:0.1.0 .
docker build -f infra/docker/knowledge-interface/Dockerfile -t exobrain/knowledge-interface:0.1.0 .
docker build -f infra/docker/metastore/db-tools/Dockerfile -t exobrain/assistant-db-tools:0.1.0 .
```

Import images into the cluster:

```bash
k3d image import \
  exobrain/assistant-frontend:0.1.0 \
  exobrain/assistant-backend:0.1.0 \
  exobrain/knowledge-interface:0.1.0 \
  exobrain/assistant-db-tools:0.1.0 \
  -c exobrain-dev
```

### 3) Deploy the Helm chart

```bash
helm upgrade --install exobrain infra/helm/exobrain-stack --dependency-update
```

To force a full rollout (to recreate pods with newly pulled Docker images):

```bash
kubectl rollout restart deployment
```

### 4) Run assistant database jobs

Run migrations:

```bash
./scripts/k3d/assistant-db-migrate.sh
```

Optional seed:

```bash
./scripts/k3d/assistant-db-seed.sh
```

Or both in order:

```bash
./scripts/k3d/assistant-db-setup.sh
```

### 5) Validate deployment

```bash
kubectl get pods
kubectl get svc
```

### 6) Access services via ingress

- Frontend: `http://localhost:8080/`
- Backend API: `http://localhost:8080/api`

Ingress is path-based (`/api` to backend, everything else to frontend).

## References

- Root index: [`README.md`](../../README.md)
- Local app-native workflow: [`local-setup.md`](local-setup.md)
- Local process orchestration: [`process-orchestration.md`](process-orchestration.md)
- Codex/cloud-agent runbook: [`../agents/codex-runbook.agent.md`](../agents/codex-runbook.agent.md)
