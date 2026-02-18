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

For command walkthroughs and known caveats, see `docs/codex-runbook.md`.

### Infra expectations

Native services are not started automatically. Start only what your task requires:

- Postgres (`postgresql`)
- NATS (`nats-server`)
- Qdrant (`qdrant`)

Assume constrained, pre-provisioned environments. Do not rely on internet installs as default workflow.

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
