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
