# model-provider

OpenAI-compatible gateway that maps internal model aliases to upstream providers.

## Endpoints

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/embeddings`

## Behavior

### Structured output (JSON schema)

`POST /v1/chat/completions` accepts OpenAI-style `response_format` for structured JSON output:

- `response_format.type`: `json_schema`
- `response_format.json_schema`: object with `name`, `schema`, and optional `strict`

Provider behavior:

- OpenAI: `response_format` is passed through directly to the OpenAI API.
- Anthropic: `response_format.json_schema` is translated to Anthropic's output configuration.

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

## Local run

```bash
./scripts/local/build-model-provider.sh
./scripts/local/run-model-provider.sh
```

Set env vars from `.env.example`.


Provider adapters use the official provider SDKs (`openai`, `anthropic`) for request/response schema compatibility.

OpenAI chat aliases should use `max_completion_tokens` defaults (not `max_tokens`) for GPT-5 compatibility.
