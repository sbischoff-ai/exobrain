# Knowledge update SSE contract (`GET /api/knowledge/update/{job_id}/watch`)

## Why this exists

Knowledge updates are asynchronous jobs owned by job-orchestrator. This document is the wire-level contract for watching job state transitions over Server-Sent Events (SSE) so backend and frontend behavior stays deterministic, especially during reconnects.

## Scope

- Endpoint: `GET /api/knowledge/update/{job_id}/watch`
- Response content type: `text/event-stream`
- Audience: assistant-backend and assistant-frontend engineers
- Covers event schemas, state mapping, ordering/termination guarantees, and reconnect behavior

## Transport framing

Each SSE event is emitted as:

- `event: <name>`
- `data: <json payload>`
- blank line terminator

Current backend behavior emits `status` events and then a terminal `done` event when the job reaches a terminal lifecycle state.

## Event names and payload schemas

Recommended event-name set for consumers: `status`, `error`, `done`.

### `status`

Emitted for each orchestrator lifecycle update.

```json
{
  "job_id": "job_01HZZZ...",
  "state": "STARTED",
  "attempt": 1,
  "detail": "worker picked up job",
  "terminal": false,
  "emitted_at": "2026-02-20T10:21:32.123Z"
}
```

Schema:

- `job_id` (`string`): watched job id
- `state` (`string`): gRPC lifecycle enum name (`ENQUEUED_OR_PENDING`, `STARTED`, `RETRYING`, `SUCCEEDED`, `FAILED_FINAL`)
- `attempt` (`integer`): worker attempt number
- `detail` (`string`): best-effort status detail (can be empty)
- `terminal` (`boolean`): true only for final lifecycle update
- `emitted_at` (`string`, RFC3339 timestamp): orchestrator event emission time

### `error` (recommended)

Reserved for stream-level, non-terminal delivery errors surfaced on the SSE channel.

```json
{
  "job_id": "job_01HZZZ...",
  "code": "UPSTREAM_UNAVAILABLE",
  "message": "knowledge update stream unavailable",
  "retryable": true
}
```

Schema:

- `job_id` (`string`): watched job id (if known)
- `code` (`string`): stable machine-readable category
- `message` (`string`): human-readable error detail
- `retryable` (`boolean`): reconnect is expected to help

> Note: current assistant-backend implementation maps most watch failures to HTTP errors (for example `404`, `403`, `503`, `502`) rather than emitting an in-band SSE `error` event.

### `done`

Emitted once when a terminal lifecycle event is observed; stream closes immediately after.

```json
{
  "job_id": "job_01HZZZ...",
  "state": "SUCCEEDED",
  "terminal": true
}
```

Schema:

- `job_id` (`string`): watched job id
- `state` (`string`): terminal lifecycle enum (`SUCCEEDED` or `FAILED_FINAL`)
- `terminal` (`boolean`): always `true`

## gRPC state mapping

`state` in SSE payloads is the direct enum name from job-orchestrator gRPC `JobLifecycleState`:

- `ENQUEUED_OR_PENDING` -> accepted/queued, not executing yet
- `STARTED` -> active execution started
- `RETRYING` -> attempt failed; orchestrator scheduled another attempt
- `SUCCEEDED` -> terminal success
- `FAILED_FINAL` -> terminal failure (no more retries)

## Ordering, termination, and reconnect guidance

### Ordering guarantees

- Events for a single `job_id` are emitted in orchestrator order.
- Every `done` event is preceded by at least one `status` event with `terminal=true` for the same state.
- Consumers must treat `status` as source-of-truth and `done` as terminal close signal.

### Termination guarantees

- On terminal lifecycle state (`SUCCEEDED` or `FAILED_FINAL`), backend emits:
  1. terminal `status`
  2. `done`
  3. stream close

### Reconnect and `include_current=true`

- Backend currently watches job status with `include_current=true`.
- Practical effect: a new watch connection receives the latest known state immediately (snapshot-style), then future transitions.
- Reconnecting after a terminal state can legitimately return terminal `status` + `done` again.
- Client guidance:
  - De-duplicate by `(job_id, state, attempt, emitted_at)` if needed.
  - Treat terminal states as idempotent.
  - Use bounded reconnect/backoff for retryable transport failures.

## Full stream examples

### Success stream example

```text
event: status
data: {"job_id":"job_abc123","state":"ENQUEUED_OR_PENDING","attempt":0,"detail":"job accepted","terminal":false,"emitted_at":"2026-02-20T10:21:30.000Z"}

event: status
data: {"job_id":"job_abc123","state":"STARTED","attempt":1,"detail":"worker started","terminal":false,"emitted_at":"2026-02-20T10:21:31.000Z"}

event: status
data: {"job_id":"job_abc123","state":"SUCCEEDED","attempt":1,"detail":"knowledge update complete","terminal":true,"emitted_at":"2026-02-20T10:21:34.000Z"}

event: done
data: {"job_id":"job_abc123","state":"SUCCEEDED","terminal":true}

```

### Failure stream example

```text
event: status
data: {"job_id":"job_def456","state":"ENQUEUED_OR_PENDING","attempt":0,"detail":"job accepted","terminal":false,"emitted_at":"2026-02-20T11:00:00.000Z"}

event: status
data: {"job_id":"job_def456","state":"STARTED","attempt":1,"detail":"worker started","terminal":false,"emitted_at":"2026-02-20T11:00:02.000Z"}

event: status
data: {"job_id":"job_def456","state":"RETRYING","attempt":1,"detail":"qdrant timeout; retry scheduled","terminal":false,"emitted_at":"2026-02-20T11:00:08.000Z"}

event: status
data: {"job_id":"job_def456","state":"STARTED","attempt":2,"detail":"retry attempt started","terminal":false,"emitted_at":"2026-02-20T11:00:12.000Z"}

event: status
data: {"job_id":"job_def456","state":"FAILED_FINAL","attempt":2,"detail":"memgraph unavailable","terminal":true,"emitted_at":"2026-02-20T11:00:20.000Z"}

event: done
data: {"job_id":"job_def456","state":"FAILED_FINAL","terminal":true}

```

## References

- Router: `apps/assistant-backend/app/api/routers/knowledge.py`
- Stream event encoding/types: `apps/assistant-backend/app/services/knowledge_stream.py`
- Watch lifecycle mapping: `apps/assistant-backend/app/services/knowledge_service.py`
