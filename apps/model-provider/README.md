# model-provider

OpenAI-compatible gateway that maps internal model aliases to upstream providers.

## Endpoints

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/embeddings`

## Local run

```bash
cd apps/model-provider
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8010
```

Set env vars from `.env.example`.
