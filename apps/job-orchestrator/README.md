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
cp .env.example .env
uv sync --extra dev
uv run python -m app.main_worker
```

To run the orchestrator API only:

```bash
cd apps/job-orchestrator
cp .env.example .env
uv sync --extra dev
uv run python -m app.main_api
```

The gRPC `EnqueueJob` endpoint validates `job_type` and payload schema before publishing `JobEnvelope` messages to JetStream subjects shaped as `jobs.<job_type>.requested`. Job IDs are generated server-side as UUIDs and returned in the RPC response.

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
- `JOB_ORCHESTRATOR_API_HOST` (default: `0.0.0.0`)
- `JOB_ORCHESTRATOR_API_PORT` (default: `50061`)
- `KNOWLEDGE_INTERFACE_GRPC_TARGET` (default: `localhost:50051`)
- `KNOWLEDGE_INTERFACE_CONNECT_TIMEOUT_SECONDS` (default: `5.0`)
- `APP_ENV` (default: `local`, influences default logging level)
- `LOG_LEVEL` (optional override; defaults to `DEBUG` in local, `INFO` otherwise)
- `RESHAPE_SCHEMA_QUERY` (optional)

## Related docs

- Docs hub: [`../../docs/README.md`](../../docs/README.md)
- Metastore migrations: [`../../infra/metastore/job-orchestrator/README.md`](../../infra/metastore/job-orchestrator/README.md)


## Troubleshooting

- If `knowledge.update` retries with timeout errors, verify `KNOWLEDGE_INTERFACE_GRPC_TARGET` points to a reachable knowledge-interface gRPC endpoint.
