# Exobrain Job Orchestrator

Python service responsible for asynchronous job orchestration.

## What this service is

- Subscribes to NATS job request subjects.
- Persists job lifecycle state in `job_orchestrator_db`.
- Executes worker job scripts idempotently, retries failures, and publishes completion/failure events.
- The `knowledge.update` skeleton uses `grpcio`; ensure `libstdc++` is available in runtime/dev environments.
- Uses an orchestration/runner abstraction so local process execution can later switch to pod orchestration.

## Quick start

For shared local startup instructions, use the canonical workflow docs:

- [`../../docs/development/local-setup.md`](../../docs/development/local-setup.md)
- [`../../docs/development/process-orchestration.md`](../../docs/development/process-orchestration.md)

To run the worker only:

```bash
cd apps/job-orchestrator
uv sync --extra dev
uv run python -m app.main_worker
```

## Common commands

Apply local migrations:

```bash
./scripts/local/job-orchestrator-db-migrate.sh
```

## Configuration

- `JOB_ORCHESTRATOR_DB_DSN` (default: `postgresql://job_orchestrator:job_orchestrator@localhost:15432/job_orchestrator_db`)
- `EXOBRAIN_NATS_URL` (default: `nats://localhost:14222`)
- `JOB_QUEUE_SUBJECT` (default: `jobs.*.*.requested`)
- `JOB_EVENTS_SUBJECT_PREFIX` (default: `jobs.events`)
- `JOB_DLQ_SUBJECT` (default: `jobs.dlq`, dead-letter queue subject)
- `JOB_MAX_ATTEMPTS` (default: `3`, max delivery attempts before DLQ)

Keep request subject patterns narrow enough that they do not also match events/DLQ subjects.
- `WORKER_REPLICA_COUNT` (default: `1`, max concurrent worker processes)
- `KNOWLEDGE_INTERFACE_GRPC_TARGET` (default: `localhost:15051`)
- `KNOWLEDGE_INTERFACE_CONNECT_TIMEOUT_SECONDS` (default: `5.0`)
- `RESHAPE_SCHEMA_QUERY` (optional)

## Related docs

- Docs hub: [`../../docs/README.md`](../../docs/README.md)
- Metastore migrations: [`../../infra/metastore/job-orchestrator/README.md`](../../infra/metastore/job-orchestrator/README.md)
