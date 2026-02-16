# Exobrain Assistant Backend

FastAPI service for chat orchestration and GraphRAG context augmentation.

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

- Assistant backend API: `http://localhost:8000`

### Infrastructure dependencies (default script wiring)

- PostgreSQL: `localhost:15432`
- Qdrant: `localhost:16333` (HTTP), `localhost:16334` (gRPC)
- Memgraph: `localhost:17687` (Bolt), `localhost:17444` (HTTP)
- NATS: `localhost:14222` (client), `localhost:18222` (monitoring)

## Kubernetes baseline

The project local cluster helper (`scripts/k3d-up.sh`) defaults to:

- Kubernetes image: `rancher/k3s:v1.35.1-k3s1`
- Local LoadBalancer mapping: `localhost:8080 -> :80`, `localhost:8443 -> :443`
