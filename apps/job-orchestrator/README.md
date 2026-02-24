# Exobrain Job Orchestrator

Python service responsible for asynchronous job orchestration.

## Responsibilities

- Subscribe to NATS job request subjects.
- Persist job lifecycle state in `job_orchestrator_db` (Postgres metastore server).
- Execute handlers idempotently and publish completion/failure events.

The service runs as a worker process today and is structured so API and worker runtimes can be split into independently-scaled deployments later.

## Environment variables

- `JOB_ORCHESTRATOR_DB_DSN` (default: `postgresql://job_orchestrator:job_orchestrator@localhost:15432/job_orchestrator_db`)
- `EXOBRAIN_NATS_URL` (default: `nats://localhost:14222`)
- `JOB_QUEUE_SUBJECT` (default: `jobs.>`)
- `JOB_EVENTS_SUBJECT_PREFIX` (default: `jobs.events`)
- `RESHAPE_SCHEMA_QUERY` (optional)

## Local run

```bash
cd apps/job-orchestrator
uv sync --extra dev
uv run python -m app.main_worker
```

## Migrations

Reshape migrations live under `infra/metastore/job-orchestrator/migrations` and target `job_orchestrator_db`.
Apply locally with:

```bash
./scripts/local/job-orchestrator-db-migrate.sh
```
