# Local Process Orchestration

## Why this exists

This guide defines the canonical way to start Exobrain processes for local development without duplicating startup instructions across service READMEs.

## Scope

- Local app-native development on a workstation.
- Command ownership for `scripts/local`, `scripts/agent`, and `scripts/k3d`.
- `mprocs` usage for first-party application processes.

## Standard workflow and ownership

### Runtime boundaries

- **Docker Compose** (`./scripts/local/infra-up.sh`): infrastructure services only (Postgres, Redis, NATS, Qdrant, Memgraph).
- **mprocs** (`./scripts/local/run-backend-suite.sh`, `./scripts/local/run-fullstack-suite.sh`): Exobrain application processes.
- **Frontend optionality**: when testing backend behavior, use the backend suite and run no frontend process.

### mprocs config files

- `.mprocs/backend.yml`: model-provider + assistant-backend + job-orchestrator
- `.mprocs/backend-knowledge.yml`: model-provider + assistant-backend + knowledge-interface + job-orchestrator
- `.mprocs/fullstack.yml`: model-provider + assistant-backend + knowledge-interface + job-orchestrator + assistant-frontend

## Script ownership matrix

| Script family     | Primary use                                | Notes                                                     |
| ----------------- | ------------------------------------------ | --------------------------------------------------------- |
| `scripts/local/*` | Workstation local development              | Uses Docker Compose for infra plus native app processes.  |
| `scripts/agent/*` | Codex/cloud-agent constrained environments | Avoids Docker/k3d assumptions; uses native infra helpers. |
| `scripts/k3d/*`   | Local Kubernetes verification              | Complements `docs/development/k3d-workflow.md`.           |

## Operational checklist

1. Start infra (`./scripts/local/infra-up.sh`).
2. Run per-database setup scripts needed for your profile (`assistant-db-setup.sh`, `job-orchestrator-db-setup.sh`, `knowledge-schema-setup.sh`).
3. Start app processes via mprocs wrapper script (ensure `job-orchestrator` is up before testing assistant knowledge updates).
4. Use `Ctrl+C` in mprocs to stop app processes.
5. Stop infra (`./scripts/local/infra-down.sh`).

Knowledge update enqueue path (canonical):

```text
assistant-backend -> job-orchestrator (gRPC EnqueueJob) -> JetStream jobs.<job_type>.requested -> worker consume/process
```

## Troubleshooting quick hits

- **`mprocs: command not found`**: run via `nix-shell` so `shell.nix` tooling is loaded.
- **Port in use**: stop previous local processes on `8000`, `50051`, `5173`, or update script env vars.
- **Backend integration errors about missing tables**: rerun `./scripts/local/assistant-db-setup.sh`.
- **Knowledge interface embedding errors**: ensure `model-provider` is running and `MODEL_PROVIDER_BASE_URL` points to it.

## References

- Local setup guide: [`local-setup.md`](./local-setup.md)
- k3d workflow: [`k3d-workflow.md`](./k3d-workflow.md)
- Codex agent workflow: [`../agents/codex-runbook.agent.md`](../agents/codex-runbook.agent.md)
