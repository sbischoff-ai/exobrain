# Chat stream SSE contract (`GET /api/chat/stream/{stream_id}`)

## Why this exists

The assistant stream interleaves text generation with tool lifecycle updates. This document is the source of truth for the SSE wire contract so backend and frontend can map tool responses deterministically and avoid UI race conditions.

## Scope

- Endpoint: `GET /api/chat/stream/{stream_id}`.
- Audience: assistant-backend and assistant-frontend engineers.
- Covers payload schemas, ordering guarantees, and correlation behavior.

## Standard / Policy / Design

### Transport framing

- Response content type: `text/event-stream`.
- Each event is emitted as:
  - `event: <type>`
  - `data: <json payload>`
  - blank line terminator
- Stream is initiated by first calling `POST /api/chat/message` and using the returned `stream_id`.

### Event types and payloads

#### `tool_call`

Emitted when the model requests a tool invocation.

```json
{
  "tool_call_id": "tc-123",
  "title": "Web search",
  "description": "Searching the web for moon landing timeline"
}
```

- `tool_call_id` is the correlation ID for this tool lifecycle.
- Frontends should create/update a pending status box keyed by `tool_call_id`.

#### `tool_response`

Emitted when a tool call completes successfully.

```json
{
  "tool_call_id": "tc-123",
  "message": "Found 4 candidate sources"
}
```

- Must be mapped to the matching pending tool box by `tool_call_id`.

#### `error`

Emitted for stream errors and for tool-specific errors.

```json
{
  "tool_call_id": "tc-123",
  "message": "Couldn't complete web search for moon landing timeline: timeout"
}
```

or stream-level error:

```json
{
  "tool_call_id": null,
  "message": "assistant stream disconnected"
}
```

- `tool_call_id` is optional/nullable because some errors are not associated with a single tool call.

#### `message_chunk`

Emitted for incremental assistant text.

```json
{
  "text": "Here's what I found..."
}
```

#### `done`

Emitted exactly once as terminal completion signal.

```json
{
  "reason": "complete"
}
```

### Ordering and correlation guarantees

- Tool-call correlation is deterministic via `tool_call_id`.
- Event arrival order across different event types may interleave with text chunks.
- Multiple tool calls may be pending simultaneously; consumers must not assume LIFO/FIFO matching.
- Consumers should prefer ID-based matching and use fallback heuristics only for legacy payload compatibility.

### Backend mapping behavior

- Tool-call IDs originate from model tool calls (`tool_call.id`).
- Backend tracks active tool mappers keyed by `tool_call_id` and emits responses/errors with the same ID.

### Frontend mapping behavior

- On `tool_call`: append pending UI item keyed by `tool_call_id`.
- On `tool_response`: resolve only the matching pending UI item by `tool_call_id`.
- On `error` with `tool_call_id`: mark/display tool-specific error against matching ID.
- On `error` without `tool_call_id`: treat as stream-level error.

## Operational checklist

- When adding/changing SSE event fields:
  - update `app/services/chat_stream.py` typed event contracts,
  - update `app/api/schemas/chat.py` Pydantic schema docs,
  - update this file,
  - update assistant-frontend stream consumers and tests.

## References

- Router: `apps/assistant-backend/app/api/routers/chat.py`
- Event schema docs: `apps/assistant-backend/app/api/schemas/chat.py`
- Stream event types: `apps/assistant-backend/app/services/chat_stream.py`
- Tool event emission: `apps/assistant-backend/app/agents/main_assistant.py`
- Frontend consumer: `apps/assistant-frontend/src/routes/+page.svelte`
