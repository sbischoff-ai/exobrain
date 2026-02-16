# Exobrain Knowledge Interface

Rust + tonic gRPC service for GraphRAG context retrieval and knowledge-base updates.

## Local build and run

From the repository root:

```bash
./scripts/local/build-knowledge-interface.sh
./scripts/local/run-knowledge-interface.sh
```

Notes:
- Re-run the build script after source changes; Rust binaries must be recompiled.
- `cargo build --locked` reuses incremental artifacts and recompiles only what changed.

## Local environment endpoints

### Application endpoint

- Knowledge interface gRPC: `localhost:50051`

### Infrastructure dependencies (default script wiring)

- PostgreSQL: `localhost:15432`
- Qdrant: `localhost:16333` (HTTP), `localhost:16334` (gRPC)
- Memgraph: `localhost:17687` (Bolt), `localhost:17444` (HTTP)
- NATS: `localhost:14222` (client), `localhost:18222` (monitoring)

## Kubernetes baseline

The project local cluster helper (`scripts/k3d-up.sh`) defaults to:

- Kubernetes image: `rancher/k3s:v1.35.1-k3s1`
- Local LoadBalancer mapping: `localhost:8080 -> :80`, `localhost:8443 -> :443`
