# AGENTS.md

## Purpose

High-signal, repository-wide rules for coding agents.
Keep this file focused on universal constraints and pointers; put domain guardrails in scoped `AGENTS.md` files.

## Documentation standards

- Repository-wide documentation policy: `docs/standards/documentation-standards.md`
- Cross-service engineering standards: `docs/standards/engineering-standards.md`
- Documentation hub/index: `docs/README.md`
- Root README is index-first; keep procedural setup details in:
  - `docs/development/local-setup.md`
  - `docs/development/k3d-workflow.md`

## Global environment constraints

In Codex/cloud-agent environments, Docker/Kubernetes tooling is often unavailable (`docker`, `docker-compose`, `k3d`).
Prefer native-process workflows and start only required services.

For command walkthroughs, use `docs/agents/codex-runbook.agent.md`.
For workflow metadata, keep `.agent/workflows.yaml` in sync with runbook prose.

Native services are not started automatically; start only what your task needs:

- Postgres (`postgresql`)
- NATS (`nats-server`)
- Qdrant (`qdrant`)

Use Reshape for Postgres schema migrations:

```sh
reshape docs
```

## Commit conventions

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

## Scoped AGENTS files (domain guardrails)

Use these for local rules and retrospective notes:

- `apps/assistant-backend/AGENTS.md`
- `apps/assistant-frontend/AGENTS.md`
- `apps/knowledge-interface/AGENTS.md`
- `scripts/agent/AGENTS.md`

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
