# AGENTS.md

## Purpose

This file provides **high-signal instructions for coding agents** working in this repository.
Keep changes focused, minimize context bloat, and prefer concise docs over long narrative.

## Codex / Cloud Agent Environment Notes

In Codex cloud environments, **Docker and Kubernetes tooling are unavailable** (`docker`, `docker-compose`, `k3d`).
Do not rely on container workflows from `README.md` unless explicitly available.

When integration or local execution requires infrastructure services, run native processes if present in the environment:

- **Postgres** (`postgresql`)
- **NATS** (`nats-server`)
- **Qdrant** (`qdrant`)

These services are not started automatically.

> Assume agents are constrained to pre-provisioned tools/dependencies.
> Do **not** add instructions that require installing extra tooling from the internet as a normal workflow.

For focused local workflows and checks, see `docs/codex-runbook.md`.

### Postgres Migrations (Reshape)

This project uses **Reshape** for Postgres schema migrations.

If you need migration guidance:

```sh
reshape docs
```

## Documentation Hygiene for Agents

- Keep agent-facing docs short and actionable.
- Prefer checklists/commands over long prose.
- Remove outdated or duplicate instructions when touching docs.
- If you add a new context doc, link it from here and from `README.md` only when generally useful.

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

- Trigger when user names a skill or request clearly matches a listed skill.
- Open only the needed parts of `SKILL.md` and related files.
- Use the minimal set of skills required.
- If a skill is missing/unreadable, state it briefly and continue with best fallback.
