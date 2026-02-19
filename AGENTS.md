# AGENTS.md

## Purpose

High-signal instructions for coding agents in this repository.
Prioritize development workflows and accurate execution over meta-documentation.

## Codex / Cloud Agent Environment Notes

In Codex cloud environments, Docker/Kubernetes tooling is typically unavailable (`docker`, `docker-compose`, `k3d`).
Prefer native-process workflows.

For agent-focused helpers, use:

- `scripts/agent/native-infra-up.sh`
- `scripts/agent/native-infra-health.sh`
- `scripts/agent/assistant-db-setup-native.sh`
- `scripts/agent/native-infra-down.sh`

For command walkthroughs, see `docs/codex-runbook.md`.

For significant incident/fix history useful for debugging, use `docs/major-changes.md`.

### Infra expectations

Native services are not started automatically. Start only what your task requires:

- Postgres (`postgresql`)
- NATS (`nats-server`)
- Qdrant (`qdrant`)

Assume constrained, pre-provisioned environments. Do not rely on internet installs as default workflow.

### Assistant backend chat testing in agent environments

When running `apps/assistant-backend` in Codex/cloud-agent environments, set `MAIN_AGENT_USE_MOCK=true` (or rely on `scripts/local/run-assistant-backend.sh`, which defaults it when `CODEX_HOME` is set). This avoids OpenAI network/key requirements and uses file-driven responses from `MAIN_AGENT_MOCK_MESSAGES_FILE`.

### Postgres migrations (Reshape)

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

- Before running assistant-backend integration tests, always run DB setup/migrations (`assistant-db-setup-native.sh` or local equivalent); missing conversation/message tables can otherwise surface as chat/journal endpoint failures.
- For streaming endpoints, catch upstream generator failures and emit a fallback chunk instead of propagating exceptions after headers are sent; this prevents incomplete chunked-read failures in clients/tests.
- When adding/changing API endpoints or schemas, include concise FastAPI/Pydantic descriptions so Swagger output remains self-explanatory for debugging and client integration.
- Prefer shared test fixtures/utilities in `tests/conftest.py` for common fakes (for example DB boundary fakes) to avoid duplicated mock logic across test modules.
- In assistant-backend unit tests, fake only external dependencies (for example Redis/DB clients); for internal app services, compose the real services together to preserve cross-service coverage.
- Keep FastAPI routers free of direct `DatabaseService` calls; route handlers should delegate through domain services (for journals: `JournalService -> ConversationService -> DatabaseService`).
- Journal endpoints use slash-formatted references (`YYYY/MM/DD`); route declarations should use `/{reference:path}` and keep static routes (for example `/search`, `/today/messages`) declared before dynamic reference routes to avoid 404 shadowing.
- Keep assistant-backend unit tests process-free: do not spawn local services (for example `redis-server`) in unit tests; reserve real service execution for integration/system workflows.
- For assistant-backend auth/session work, remember sessions are Redis-backed via `ASSISTANT_CACHE_REDIS_URL`; keep local infra (`infra/docker-compose/local-infra.yml`), Helm values/templates, and `scripts/agent/native-infra-*` in sync to avoid environment-specific regressions.
- For logging-related changes, check and update both app-level README files and deployment manifests (Dockerfiles + Helm values/templates) in the same pass to avoid config drift.
- Frontend production logging defaults should stay conservative (`warn` or higher) unless the task explicitly asks for verbose runtime telemetry.
