# model-provider

OpenAI-compatible gateway that maps internal model aliases to upstream providers.

## Endpoints

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/embeddings`

## Local run

```bash
./scripts/local/build-model-provider.sh
./scripts/local/run-model-provider.sh
```

Set env vars from `.env.example`.


Provider adapters use the official provider SDKs (`openai`, `anthropic`) for request/response schema compatibility.

OpenAI chat aliases should use `max_completion_tokens` defaults (not `max_tokens`) for GPT-5 compatibility.
