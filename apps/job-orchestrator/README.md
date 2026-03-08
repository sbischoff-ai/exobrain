# Exobrain Job Orchestrator

Python service responsible for asynchronous job orchestration.

## What this service is

- Owns the canonical `EnqueueJob` gRPC API that producers (including `assistant-backend`) call to enqueue asynchronous work.
- Subscribes to NATS job request subjects.
- Persists job lifecycle state in `job_orchestrator_db`.
- Executes worker job scripts idempotently, retries failures, and publishes completion/failure events.
- Worker subprocess stdout/stderr is forwarded into job-orchestrator logs so `mprocs` shows per-job console output during local debugging.
- Each worker run also writes a per-job log file under `logs/jobs/` (repo root) including captured stdout/stderr for post-run inspection.
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

Implementation note: the worker is organized as a thin orchestrator in
`app/worker/jobs/knowledge_update/__init__.py` with step modules under
`app/worker/jobs/knowledge_update/steps/step01_graph_seed.py` through
`step10_mentions.py`. Shared helpers live in adjacent `core.py`, `prompts.py`,
`schemas.py`, and `types.py` modules.

0. Create chat-message graph delta (deterministic, currently disabled): code path remains in place, but execution skips this step for sparse test runs.
1. Create markdown batch document (deterministic): format the conversation into a compact LLM-friendly turn transcript.
2. Entity extraction (`worker` model): call `GetEntityExtractionSchemaContext` with `requesting_user_id`, inject context into the system prompt, and return strict structured JSON with `extracted_entities` and `extracted_universes`.
3. Entity candidate matching (deterministic): for each extracted entity, call `FindEntityCandidates` with names/aliases/description/type and classify by score thresholds (`>0.1`, `>0.6`, `>0.15`) to decide direct match vs. detailed comparison.
4. Extracted entity contexts (`reasoner` model): create focused markdown per extracted entity with heading depth up to 2 and semantically bounded paragraph/list chunks.
5. Detailed comparison (`worker` model): for entities requiring further comparison, call `GetEntityContext` (block level 1, with `requesting_user_id`) for each candidate and decide `MATCH({entity_id})` vs `NEW_ENTITY`; structured output is validated with Pydantic at the LLM boundary, and unresolved/new entities receive new UUIDs.
6. Relationship extraction (`worker` model): derive related entity pairs from markdown using the resolved entity IDs from step 5; step output is validated with typed Pydantic models before deduplication/filtering.
7. Relationship type + score (`worker` model): for each related pair, call `GetEdgeExtractionSchemaContext` (with `requesting_user_id`) and choose direction/edge type/confidence.
8. Build final entity context graphs (`worker`/`reasoner`): for each resolved entity, call `GetEntityTypePropertyContext` (with `requesting_user_id`) and produce entity + block-tree payloads; matched entities also include `GetEntityContext` (block level 2) context for minimal updates. Step-8 rejects malformed outputs that omit required entity keys (`entity_id`, `node_type`, `name`, `aliases`) and does not auto-repair those required keys.
9. Merge graph delta (deterministic): merge step-8 final entity context graphs (mapping entity/block payloads, replacing `NEW_BLOCK_N` placeholders with UUIDs), step-7 relationship edges (`status=asserted`), and step-2 fictional universes; the step-0 chat-message graph delta merge is currently disabled for sparse test runs, then validate the merged payload via protobuf `ParseDict`.
10. Finalize graph delta (`worker` model, currently disabled): mentions-finalization code remains in place, but execution currently skips adding `MENTIONS` edges for sparse test runs.
11. Graph payload preflight (deterministic): before upsert, validate each entity payload against `GetEntityTypePropertyContext` writable requirements (`required=true`, `writable=true`) and value-type compatibility, and validate every edge includes `confidence`, `status`, and `provenance_hint` with compatible value fields; fail fast with concise step-scoped diagnostics.
12. Upsert graph delta (deterministic): persist the final merged graph delta via `UpsertGraphDelta`.

Operational hardening notes for `knowledge.update`:

- Every `channel.unary_unary(...)` gRPC call and every `agent.ainvoke(...)` model-provider call is wrapped with bounded retry logic using exponential backoff plus jitter.
- Retries are limited to transient failures (timeouts, connection-establishment/transport-level issues, and 5xx-style upstream failures).
- Final failures are raised as step-scoped `KnowledgeUpdateStepError` instances carrying `step_name`, `operation`, and original exception class so logs are diagnosable without scraping full tracebacks.
- Step 8 validates required entity payload keys after normalization and fails fast instead of silently synthesizing missing core identity fields from fallback context.

## Common commands

Apply local migrations:

```bash
./scripts/local/job-orchestrator-db-migrate.sh
```

Run static checks + tests together:

```bash
cd apps/job-orchestrator && ./scripts/verify.sh
```

## Configuration

- `JOB_ORCHESTRATOR_DB_DSN` (default: `postgresql://job_orchestrator:job_orchestrator@localhost:15432/job_orchestrator_db`)
- `EXOBRAIN_NATS_URL` (default: `nats://localhost:14222`)
- `JOB_QUEUE_SUBJECT` (default: `jobs.*.*.requested`)
- `JOB_EVENTS_SUBJECT_PREFIX` (default: `jobs.events`)
- `JOB_DLQ_SUBJECT` (default: `jobs.dlq`, dead-letter queue subject)
- `JOB_MAX_ATTEMPTS` (default: `3`, max delivery attempts before DLQ)
- `JOB_CONSUMER_ACK_WAIT_SECONDS` (default: `150.0`, JetStream job lease/ack-wait timeout; keep above per-request model-provider timeout)

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
- `KNOWLEDGE_UPDATE_MODEL_PROVIDER_TIMEOUT_SECONDS` (default: `120.0`, HTTP timeout for knowledge-update model-provider calls used by entity extraction)
- `APP_ENV` (default: `local`, influences default logging level)
- `LOG_LEVEL` (optional override; defaults to `DEBUG` in local, `INFO` otherwise)
- `RESHAPE_SCHEMA_QUERY` (optional)

## Related docs

- Docs hub: [`../../docs/README.md`](../../docs/README.md)
- Metastore migrations: [`../../infra/metastore/job-orchestrator/README.md`](../../infra/metastore/job-orchestrator/README.md)

## Troubleshooting

- If `knowledge.update` retries with timeout errors, verify `KNOWLEDGE_INTERFACE_GRPC_TARGET` points to a reachable knowledge-interface gRPC endpoint. On local setups, prefer `127.0.0.1:50051` over `localhost:50051` to avoid IPv6 loopback resolution mismatches when knowledge-interface binds only on IPv4.
- If `knowledge.update` fails with `unhandled errors in a TaskGroup`, inspect the forwarded worker `stderr` traceback in orchestrator logs; worker entrypoint now emits full Python tracebacks (not just the top-level message) to pinpoint which step failed.
- If `knowledge.update` fails around entity extraction context loading, verify knowledge-interface is reachable and `GetEntityExtractionSchemaContext` can be called with the requesting user id.
- If `knowledge.update` fails with OpenAI `400 Bad Request` and `invalid_function_parameters`, verify tool/function schemas are plain JSON Schema objects (no nested OpenAI `json_schema` envelope inside `tools[].function.parameters`).
- If `knowledge.update` step 7 fails around `GetEdgeExtractionSchemaContext`, ensure the generated worker protobuf is synced with `apps/knowledge-interface/proto/knowledge.proto` (request fields must be `first_entity_type`/`second_entity_type`; response field is `edge_types`).
- Model-provider client requests intentionally omit `temperature`; alias-specific temperature behavior must be configured server-side in model-provider.
- If producers fail with `UNAVAILABLE` on `EnqueueJob`, confirm the orchestrator API process is running and reachable at `JOB_ORCHESTRATOR_API_BIND_ADDRESS` / `JOB_ORCHESTRATOR_API_PORT`.
