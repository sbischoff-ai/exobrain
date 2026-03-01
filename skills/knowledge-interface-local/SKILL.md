# knowledge-interface-local

## Use this skill when

- Task touches `apps/knowledge-interface` ingestion/query behavior.
- Task touches Memgraph/Qdrant integration or schema-derived graph semantics.
- You need local knowledge-interface runtime checks in agent/dev environments.

## Canonical references

- [`AGENTS.md`](../../AGENTS.md)
- [`docs/development/local-setup.md`](../../docs/development/local-setup.md)
- [`docs/agents/codex-runbook.agent.md`](../../docs/agents/codex-runbook.agent.md)

## Command sequence (exact repo scripts)

1. Start/check native infra required for local agent workflows:

```sh
./scripts/agent/native-infra-up.sh
./scripts/agent/native-infra-health.sh
```

2. Build knowledge-interface:

```sh
./scripts/local/build-knowledge-interface.sh
```

3. Run knowledge-interface locally (loads `apps/knowledge-interface/.env` if present):

```sh
./scripts/local/run-knowledge-interface.sh
```

4. If schema setup is required in workstation/docker workflows:

```sh
./scripts/local/knowledge-schema-setup.sh
```

## Failure handling

- **Qdrant unavailable or wrong endpoint format**
  - Use `QDRANT_ADDR` as URL format (for example `http://localhost:6334`), not bare `host:port`.
  - In native/dev contexts, verify with `./scripts/agent/native-infra-health.sh`.
- **Qdrant protocol mismatch (REST vs gRPC)**
  - Prefer gRPC-compatible port for `QDRANT_ADDR` in knowledge-interface flows.
- **Memgraph DB mismatch (`neo4j` default issues)**
  - Set `MEMGRAPH_DB=memgraph` (or deployed DB name) before startup.
- **Offline embedding requirements**
  - Set `EMBEDDING_USE_MOCK=true` to bypass external embedding providers.
- **Postgres migration tooling (`reshape`) missing when doing schema setup**
  - Confirm `reshape --help`; if unavailable, report environment blocker and avoid ad-hoc installs.

## Expected verification output

- Build script completes without Cargo compile errors.
- `run-knowledge-interface.sh` logs environment load and starts server process.
- Health checks show reachable Postgres/Qdrant/NATS when those services are required by changed paths.

## Rollback / cleanup

```sh
./scripts/agent/native-infra-down.sh
```

- Stop `cargo run` process with `Ctrl+C`.
