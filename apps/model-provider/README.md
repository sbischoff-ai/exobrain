# model-provider

OpenAI-compatible gateway that maps internal model aliases to upstream providers.

## Endpoints

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/internal/chat/messages`
- `POST /v1/embeddings`

## Behavior

### Structured output (JSON schema)

`POST /v1/chat/completions` accepts OpenAI-style `response_format` for structured JSON output:

- `response_format.type`: `json_schema`
- `response_format.json_schema`: object with `name`, `schema`, and optional `strict`

Provider behavior:

- OpenAI: `response_format` is passed through directly to the OpenAI API.
- Anthropic: `response_format.json_schema` is translated to Anthropic's output configuration.
- Anthropic: OpenAI-style string `tool_choice` values are translated (`auto`→`{"type":"auto"}`, `none`→`{"type":"none"}`, `required`→`{"type":"any"}`).
- Anthropic: OpenAI-style function tools are translated to Anthropic custom tool objects (`{"type":"function","function":{...}}` → `{"name","description","input_schema"}`).
- Anthropic: tool `input_schema` is always normalized to an object schema; non-object function `parameters` are wrapped under `{"input": ...}` for compatibility.
- Anthropic: OpenAI/LangChain tool schemas are normalized (OpenAPI-only keys removed, `definitions`→`$defs`, `$ref` inlined) and validated with JSON Schema Draft 2020-12 before request dispatch; invalid schemas return HTTP 400.
- Anthropic: LangChain/OpenAI tool envelopes (`{"type":"json_schema","json_schema":{...}}`) are unwrapped to their inner `schema` before normalization to avoid invalid Anthropic tool schema errors.
- Anthropic: OpenAI-style forced function tool choice is translated (`{"type":"function","function":{"name":"X"}}`→`{"type":"tool","name":"X"}`).

Minimal example:

```json
{
  "model": "openai/gpt-4o-mini",
  "messages": [{ "role": "user", "content": "Return a status object" }],
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "status",
      "schema": {
        "type": "object",
        "properties": { "ok": { "type": "boolean" } },
        "required": ["ok"],
        "additionalProperties": false
      }
    }
  }
}
```

Invalid `response_format` payloads (for example malformed schema objects) return a 4xx validation error from the gateway or upstream provider.


### Native internal chat contract

`POST /v1/internal/chat/messages` is the provider-native internal interface. It models:

- Message blocks (`text`, `tool_result`, `tool_call`) across `system`/`user`/`assistant` messages
- Tool definitions and tool choice policy
- Structured output intent as explicit JSON schema input (native requests without a `structured_output.name` are normalized to `"structured_output"` for OpenAI compatibility)
- Streaming event frames (`text_delta`, `tool_call`, `completion`, `usage`)
- Assistant tool-call history is forwarded with `content: null` (not empty string) for OpenAI chat-completions compatibility during multi-turn tool-use loops.
- Compatibility shim message history is validated for OpenAI tool-call ordering; unresolved or out-of-order `assistant.tool_calls` now return HTTP 400 before provider dispatch.
- OpenAI streaming `tool_calls[].function.arguments` deltas are reassembled before emitting native `tool_call` frames, so downstream LangChain agents receive complete JSON arguments during tool-use turns.

`/v1/chat/completions` is retained as a compatibility shim that projects between OpenAI payloads and the internal native contract.

## Local run

```bash
./scripts/local/build-model-provider.sh
./scripts/local/run-model-provider.sh
```

Set env vars from `.env.example`.


Provider adapters use the official provider SDKs (`openai`, `anthropic`) for request/response schema compatibility.

- Provider SDK clients are process-wide singletons (per provider/api key/timeout/retry config) so concurrent requests share one OpenAI and one Anthropic client instance.
- Conservative throttling defaults are enabled per provider (`max_retries=8`, `max_concurrent_requests=2`) to reduce upstream `420/429` rate-limit failures under bursty parallel traffic.
OpenAI chat aliases should use `max_completion_tokens` defaults (not `max_tokens`) for GPT-5 compatibility.
- The `architect` alias has an in-memory token budget guard: each request payload is estimated as `round(len(payload_json)/4)` tokens and tracked in a shared process list for the last 60 seconds. If the rolling sum meets/exceeds the configured threshold, forwarding is delayed by `60s - time since previous architect request`.

Config knobs (environment variables):

- `MODEL_PROVIDER_OPENAI_MAX_RETRIES` (default `8`)
- `MODEL_PROVIDER_OPENAI_MAX_CONCURRENT_REQUESTS` (default `2`)
- `MODEL_PROVIDER_ANTHROPIC_MAX_RETRIES` (default `8`)
- `MODEL_PROVIDER_ANTHROPIC_MAX_CONCURRENT_REQUESTS` (default `2`)

- `ARCHITECT_MODEL_MAX_TOKENS_PER_MINUTE` (default `30000`)
