# Exobrain Job Orchestrator

Python service responsible for asynchronous job orchestration.

## What this service is

- Owns the canonical `EnqueueJob` gRPC API that producers (including `assistant-backend`) call to enqueue asynchronous work.
- Subscribes to NATS job request subjects.
- Persists job lifecycle state in `job_orchestrator_db`.
- Executes worker job scripts idempotently, retries failures, and publishes completion/failure events.
- Worker subprocess stdout/stderr is forwarded into job-orchestrator logs so `mprocs` shows per-job console output during local debugging.
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

The gRPC API exposes:

- `EnqueueJob` to validate `job_type` and payload schema before publishing `JobEnvelope` messages to JetStream subjects shaped as `jobs.<job_type>.requested`.
- `GetJobStatus` to fetch the latest canonical lifecycle snapshot for a job.
- `WatchJobStatus` to stream lifecycle events for a job, optionally including the current snapshot first.

Job IDs are generated server-side as UUIDs and returned in the enqueue response. Status APIs normalize lifecycle states to user-visible values: `ENQUEUED_OR_PENDING`, `STARTED`, `RETRYING`, `SUCCEEDED`, and `FAILED_FINAL`.

Persistence distinguishes retryable and terminal failures: retryable failures keep `status='failed'` with `is_terminal=false`, while max-attempt/DLQ failures set `is_terminal=true` and `terminal_reason='max-attempts'`.

Lifecycle status events are published on job-scoped subjects (`jobs.status.<job_id>`) so `WatchJobStatus` can subscribe narrowly and terminate after terminal events (`SUCCEEDED` or `FAILED_FINAL`).

### GetJobStatus

`GetJobStatus` returns a single snapshot for `job_id`.

- Request: `GetJobStatusRequest { job_id }`
- Success response: `GetJobStatusReply { job_id, state, attempt, detail, terminal, updated_at }`
- Validation/lookup behavior:
  - Invalid UUID job IDs return `INVALID_ARGUMENT`.
  - Unknown job IDs return `NOT_FOUND`.

The `state` value is normalized from stored lifecycle rows:

- `requested`/`pending`/`enqueued_or_pending` -> `ENQUEUED_OR_PENDING`
- `processing`/`started` -> `STARTED`
- `retrying` -> `RETRYING`
- `completed`/`succeeded` -> `SUCCEEDED`
- `failed` with `is_terminal=false` -> `RETRYING`
- `failed` with `is_terminal=true` -> `FAILED_FINAL`

`FAILED_FINAL` specifically means max attempts were exhausted and the job was handed off to DLQ flow (`terminal_reason='max-attempts'`).

### WatchJobStatus

`WatchJobStatus` opens a server stream of `JobStatusEvent` messages for a single `job_id`.

- Request: `WatchJobStatusRequest { job_id, include_current }`
- Stream response item: `JobStatusEvent { job_id, state, attempt, detail, terminal, emitted_at }`
- Validation/lookup behavior:
  - Invalid UUID job IDs return `INVALID_ARGUMENT`.
  - If `include_current=true` and the job is unknown, returns `NOT_FOUND`.

Streaming semantics:

- If `include_current=true`, the API emits the current snapshot first.
- After the optional snapshot, the API subscribes to lifecycle status events for that exact job and forwards matching events in order.
- The stream stays open for non-terminal states (`ENQUEUED_OR_PENDING`, `STARTED`, `RETRYING`) and closes only after a terminal event (`SUCCEEDED` or `FAILED_FINAL`).
- If the first emitted snapshot is already terminal, the stream closes immediately after that event.

Observability/debugging note:

- Status events are emitted to job-scoped NATS subjects (`jobs.status.<job_id>`), which keeps `WatchJobStatus` subscriptions narrow and makes per-job tracing straightforward in NATS tooling.

Request flow:

```text
assistant-backend
  -> job-orchestrator EnqueueJob (gRPC)
  -> JetStream subject jobs.<job_type>.requested
  -> job-orchestrator worker consume/process/retry
```

This API ownership keeps producers decoupled from JetStream subject/version details and lets the orchestrator enforce payload validation centrally.
For `knowledge.update`, clients must provide `user_id` plus the typed `knowledge_update` payload (`journal_reference`, `messages`, and `requested_by_user_id`), and the server uses `user_id` as the envelope correlation id.
Current `knowledge.update` worker flow uses explicit small steps:

0. Create chat-message graph delta (deterministic): map payload messages into `node.chat_message` + `node.block` with `SENT_TO` / `SENT_BY` / `DESCRIBED_BY` edges.
1. Create markdown batch document (deterministic): format the conversation into a compact LLM-friendly turn transcript.
2. Entity extraction (`worker` model): call `GetEntityExtractionSchemaContext` with `requesting_user_id`, inject context into the system prompt, and return strict structured JSON with `extracted_entities` and `extracted_universes`.
3. Entity candidate matching (deterministic): for each extracted entity, call `FindEntityCandidates` with names/aliases/description/type and classify by score thresholds (`>0.1`, `>0.6`, `>0.15`) to decide direct match vs. detailed comparison.
4. Extracted entity contexts (`reasoner` model): create focused markdown per extracted entity with heading depth up to 2 and semantically bounded paragraph/list chunks.
5. Detailed comparison (`worker` model): for entities requiring further comparison, call `GetEntityContext` (block level 1, with `requesting_user_id`) for each candidate and decide `MATCH({entity_id})` vs `NEW_ENTITY`; unresolved/new entities receive new UUIDs.
6. Relationship extraction (`worker` model): derive related entity pairs from markdown using the resolved entity IDs from step 5.
7. Relationship type + score (`worker` model): for each related pair, call `GetEdgeExtractionSchemaContext` (with `requesting_user_id`) and choose direction/edge type/confidence.
8. Build final entity context graphs (`worker`/`reasoner`): for each resolved entity, call `GetEntityTypePropertyContext` (with `requesting_user_id`) and produce entity + block-tree payloads; matched entities also include `GetEntityContext` (block level 2) context for minimal updates.
9. Merge graph delta (deterministic): merge step-0 chat-message graph delta with step-8 final entity context graphs (mapping entity/block payloads, replacing `NEW_BLOCK_N` placeholders with UUIDs), step-7 relationship edges (`status=asserted`), and step-2 fictional universes.
10. Finalize graph delta (`worker` model): detect block-to-entity mentions and append `MENTIONS` edges with confidence and `status=asserted`.
11. Upsert graph delta (deterministic): persist the final merged graph delta via `UpsertGraphDelta`.

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
- `JOB_ORCHESTRATOR_API_BIND_ADDRESS` (optional explicit bind target, e.g. `0.0.0.0:50061`)
- `JOB_ORCHESTRATOR_API_HOST` (default: `0.0.0.0`, used when bind address not set)
- `JOB_ORCHESTRATOR_API_PORT` (default: `50061`, used when bind address not set)
- `JOB_ORCHESTRATOR_API_ENABLED` (default: `true`, run API process)
- `JOB_ORCHESTRATOR_WORKER_ENABLED` (default: `true`, run worker process)
- `KNOWLEDGE_INTERFACE_GRPC_TARGET` (default: `localhost:50051`)
- `KNOWLEDGE_INTERFACE_CONNECT_TIMEOUT_SECONDS` (default: `5.0`)
- `MODEL_PROVIDER_BASE_URL` (default: `http://localhost:8010/v1`, model-provider base API URL; clients append `/internal/chat/messages` for the native chat contract used by step-two entity extraction, step-four context extraction, and step-five detailed comparison)
- `KNOWLEDGE_UPDATE_EXTRACTION_MODEL` (default: `worker`, model alias used for step-two entity extraction)
- `KNOWLEDGE_UPDATE_MODEL_PROVIDER_TIMEOUT_SECONDS` (default: `100.0`, HTTP timeout for knowledge-update model-provider calls used by entity extraction)
- `APP_ENV` (default: `local`, influences default logging level)
- `LOG_LEVEL` (optional override; defaults to `DEBUG` in local, `INFO` otherwise)
- `RESHAPE_SCHEMA_QUERY` (optional)

## Related docs

- Docs hub: [`../../docs/README.md`](../../docs/README.md)
- Metastore migrations: [`../../infra/metastore/job-orchestrator/README.md`](../../infra/metastore/job-orchestrator/README.md)

## Troubleshooting

- If `knowledge.update` retries with timeout errors, verify `KNOWLEDGE_INTERFACE_GRPC_TARGET` points to a reachable knowledge-interface gRPC endpoint.
- If `knowledge.update` fails with `unhandled errors in a TaskGroup`, inspect the forwarded worker `stderr` traceback in orchestrator logs; worker entrypoint now emits full Python tracebacks (not just the top-level message) to pinpoint which step failed.
- If `knowledge.update` fails around entity extraction context loading, verify knowledge-interface is reachable and `GetEntityExtractionSchemaContext` can be called with the requesting user id.
- If producers fail with `UNAVAILABLE` on `EnqueueJob`, confirm the orchestrator API process is running and reachable at `JOB_ORCHESTRATOR_API_BIND_ADDRESS` / `JOB_ORCHESTRATOR_API_PORT`.
