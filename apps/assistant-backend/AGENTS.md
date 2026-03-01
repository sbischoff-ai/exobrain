# AGENTS.md (assistant-backend scope)

Applies to `apps/assistant-backend/**`.

## Local workflow guardrails

- In Codex/cloud-agent environments, set `MAIN_AGENT_USE_MOCK=true` for chat testing, or use `scripts/local/run-assistant-backend.sh` (defaults to mock mode when `CODEX_HOME` is set).
- In pyenv-shimmed containers, prefer project-venv execution:
  - `uv sync --extra dev`
  - `uv run python -m pytest`

## Architecture and API conventions

- Keep chat request orchestration in `ChatService` (not routers); wire `chat_service` through `app.state` like other services.
- Keep FastAPI routers free of direct `DatabaseService` calls; route handlers should delegate through domain services.
- Journal endpoints use slash-formatted references (`YYYY/MM/DD`):
  - Use `/{reference:path}` for dynamic reference routes.
  - Declare static routes (for example `/search`, `/today/messages`) before dynamic reference routes.
- For API endpoint/schema updates, include concise FastAPI/Pydantic descriptions so Swagger stays self-explanatory.

## Testing conventions

- Before integration tests, run DB setup/migrations (`scripts/agent/assistant-db-setup-native.sh` or local equivalent).
- Prefer shared fixtures/utilities in `tests/conftest.py` for common fakes.
- In unit tests, fake only external dependencies (DB/Redis clients); compose internal services together where possible.
- Keep unit tests process-free (do not spawn services such as `redis-server`).

## Ops and config alignment

- Session/auth changes rely on Redis via `ASSISTANT_CACHE_REDIS_URL`; keep env assumptions aligned with infra manifests and scripts.
- For logging-related changes, update app README + deployment manifests (Dockerfiles/Helm values/templates) together.
- For prompt-formatting changes involving math rendering, require display math as block math (`$$...$$`) with surrounding blank lines.
- Assistant metastore seeds are ordered and multi-file (`infra/metastore/assistant-backend/seeds/*.sql`); use reset/seed scripts when refreshing datasets.
