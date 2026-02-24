# AGENTS.md

## Purpose

High-signal instructions for coding agents in this repository.
Prioritize development workflows and accurate execution over meta-documentation.

## Documentation standards

- Repository-wide documentation policy: `docs/standards/documentation-standards.md`
- Cross-service engineering standards: `docs/standards/engineering-standards.md`
- Documentation hub/index: `docs/README.md`
- Root README is index-first; keep procedural setup details in `docs/development/local-setup.md` and `docs/development/k3d-workflow.md`.

## Codex / Cloud Agent Environment Notes

In Codex cloud environments, Docker/Kubernetes tooling is typically unavailable (`docker`, `docker-compose`, `k3d`).
Prefer native-process workflows.

For agent-focused helpers, use:

- `scripts/agent/native-infra-up.sh`
- `scripts/agent/native-infra-health.sh`
- `scripts/agent/assistant-db-setup-native.sh`
- `scripts/agent/native-infra-down.sh`

For command walkthroughs, see `docs/agents/codex-runbook.agent.md`.

For significant incident/fix history useful for debugging, use `docs/operations/major-changes.md`.

### Infra expectations

Native services are not started automatically. Start only what your task requires:

- Postgres (`postgresql`)
- NATS (`nats-server`)
- Qdrant (`qdrant`)

Assume constrained, pre-provisioned environments. Do not rely on internet installs as default workflow.

### Assistant backend chat testing in agent environments

When running `apps/assistant-backend` in Codex/cloud-agent environments, set `MAIN_AGENT_USE_MOCK=true` (or rely on `scripts/local/run-assistant-backend.sh`, which defaults it when `CODEX_HOME` is set). This avoids OpenAI network/key requirements and uses file-driven responses from `MAIN_AGENT_MOCK_MESSAGES_FILE`.

### Postgres migrations (Reshape)

- In Codex containers with pyenv shims, `python3` may resolve to 3.10 even when `/usr/bin/python3.12` exists; run backend tests from `apps/assistant-backend` after `uv sync --extra dev` so `uv run` uses the project `.venv` (3.12) and prefer `uv run python -m pytest` if command resolution is ambiguous.


This repository uses Reshape for Postgres schema migrations:

```sh
reshape docs
```

## Commit Conventions

Use Conventional Commits.

### Format (required)

`<type>(<scope>): <subject>`

### Allowed types

- feat
- fix
- refactor
- perf
- test
- docs
- build
- ci
- chore
- style
- revert

### Allowed scopes (required)

- assistant
- knowledge
- infra
- tooling
- misc

### Subject rules

- Imperative mood (e.g. "add", "fix", "remove")
- No trailing period
- Max 72 chars

### Hygiene

- Do not commit generated build artifacts
- Do not commit secrets
- Keep diffs focused

- Keep assistant-frontend route components thin by moving API calls/business flows into `src/lib/services` and persistence mechanics into `src/lib/stores`; reserve `src/lib/models` for shared typed payload contracts.

## Skills

A skill is a set of local instructions in a `SKILL.md` file.

### Available skills

- `skill-creator`: `/opt/codex/skills/.system/skill-creator/SKILL.md`
- `skill-installer`: `/opt/codex/skills/.system/skill-installer/SKILL.md`

### How to use skills

- Trigger when the user names a skill or the request clearly matches one.
- Open only needed parts of skill docs/references.
- Use the minimal set of skills required.
- If a skill is missing/unreadable, state it briefly and proceed with best fallback.

## Agent retrospective notes

- Keep chat request orchestration in `ChatService` (not chat router), and wire `chat_service` through `app.state` like other services rather than ad-hoc cached factories.
- Before running assistant-backend integration tests, always run DB setup/migrations (`assistant-db-setup-native.sh` or local equivalent); missing conversation/message tables can otherwise surface as chat/journal endpoint failures.
- When adding/changing API endpoints or schemas, include concise FastAPI/Pydantic descriptions so Swagger output remains self-explanatory for debugging and client integration.
- Prefer shared test fixtures/utilities in `tests/conftest.py` for common fakes (for example DB boundary fakes) to avoid duplicated mock logic across test modules.
- In assistant-backend unit tests, fake only external dependencies (for example Redis/DB clients); for internal app services, compose the real services together to preserve cross-service coverage.
- Keep FastAPI routers free of direct `DatabaseService` calls; route handlers should delegate through domain services (for journals: `JournalService -> ConversationService -> DatabaseService`).
- Journal endpoints use slash-formatted references (`YYYY/MM/DD`); route declarations should use `/{reference:path}` and keep static routes (for example `/search`, `/today/messages`) declared before dynamic reference routes to avoid 404 shadowing.
- Keep assistant-backend unit tests process-free: do not spawn local services (for example `redis-server`) in unit tests; reserve real service execution for integration/system workflows.
- For assistant-backend auth/session work, remember sessions are Redis-backed via `ASSISTANT_CACHE_REDIS_URL`; keep local infra (`infra/docker-compose/local-infra.yml`), Helm values/templates, and `scripts/agent/native-infra-*` in sync to avoid environment-specific regressions.
- For logging-related changes, check and update both app-level README files and deployment manifests (Dockerfiles + Helm values/templates) in the same pass to avoid config drift.
- Frontend production logging defaults should stay conservative (`warn` or higher) unless the task explicitly asks for verbose runtime telemetry.
- Assistant frontend now relies on cookie-authenticated intro gating plus `sessionStorage` journal snapshots (`exobrain.assistant.session`); keep journal UI changes aligned with the startup sync contract (`/api/journal/{reference}` `message_count` check + fallback seed from `/api/journal/today`).
- Assistant frontend message APIs are newest-first for pagination; normalize fetched message lists to chronological order before rendering so chat always grows downward.
- Chat view auto-scroll should react to every message update (not just loading state), including streamed assistant chunk updates, so the viewport continuously follows long replies.

- In assistant-frontend, logout should clear `sessionStorage` journal snapshots and send users back to the intro gate; user-menu dropdowns in the main shell should stay logout-focused (no duplicate login UX there).

- Journal overlay UX should behave as a non-layout-shifting drawer (chat stays centered), with compact chevron controls and an explicitly button-like highlighted today entry for quick orientation.

- Journal drawer controls should be viewport-anchored on the left edge (not container-anchored), while the chat panel remains centered independently.
- Assistant metastore seeds are ordered and multi-file (`infra/metastore/assistant-backend/seeds/*.sql`); use `scripts/local/assistant-db-reset-and-seed.sh` (or native equivalent) when refreshing test datasets.

- Metastore bootstrap SQL is now split per database (`01-assistant-db.sql`, `02-job-orchestrator-db.sql`, `03-knowledge-schema-db.sql`); keep script defaults and Helm DB migration job env values synchronized when role/database settings change.

- In coding-agent environments, prefer `scripts/agent/run-assistant-frontend-mock.sh` for frontend-only UI exploration and `scripts/agent/run-assistant-backend-offline.sh` for backend runs that must avoid OpenAI/Tavily network dependencies.
- Knowledge-interface local dev should load `apps/knowledge-interface/.env`; keep gRPC reflection local-only (`APP_ENV=local`) so `grpcui` works in dev without exposing reflection in cluster/runtime manifests.
- Knowledge-interface gRPC is pre-launch and may use clean breaking changes; prefer schema-driven property payloads over hard-coded entity/event fields when evolving ingestion contracts.
- For assistant-frontend E2E validation in agent environments, use `scripts/agent/run-assistant-frontend-e2e.sh` (Playwright against mock API mode) before finalizing UI/UX changes.
- Knowledge-interface universe semantics: IDs are globally unique across universes and cross-universe graph edges are intentional; treat universes primarily as filtering/context semantics, and keep ingestion `labels` documented as currently unused forward-compat fields unless explicitly implementing label-aware writes.

- Local workstation startup now defaults to Docker Compose infra plus `mprocs` app orchestration; keep `.mprocs/*.yml` and `scripts/local/run-*-suite.sh` aligned when adding/removing services.

- In job-orchestrator, avoid broad `JOB_QUEUE_SUBJECT` patterns that also match result/DLQ subjects; keep request subscription scoped (for example `jobs.*.*.requested`) to prevent self-consumption loops.

- When changing `JOB_QUEUE_SUBJECT` filtering semantics, rotate `JOB_CONSUMER_DURABLE` (or recreate the consumer) so old JetStream consumer filters do not persist and cause unexpected message fan-in.

- If worker flows rely on native `grpcio`, ensure runtime libraries are provisioned (for example `libstdc++.so.6` in Docker images and local dev shells).

- For worker subprocess jobs, emit concise stderr errors (avoid full tracebacks for expected connectivity timeouts) so orchestrator logs stay actionable during retries.
