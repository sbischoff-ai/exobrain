# Exobrain Job Orchestrator

Python service responsible for asynchronous job orchestration.

## What this service is

- Subscribes to NATS job request subjects.
- Persists job lifecycle state in `job_orchestrator_db`.
- Executes handlers idempotently and publishes completion/failure events.

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
- `JOB_QUEUE_SUBJECT` (default: `jobs.>`)
- `JOB_EVENTS_SUBJECT_PREFIX` (default: `jobs.events`)
- `RESHAPE_SCHEMA_QUERY` (optional)

## Related docs

- Docs hub: [`../../docs/README.md`](../../docs/README.md)
- Metastore migrations: [`../../infra/metastore/job-orchestrator/README.md`](../../infra/metastore/job-orchestrator/README.md)
