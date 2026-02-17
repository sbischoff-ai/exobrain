# AGENTS.md

## Codex / Cloud Agent Environment Notes

When working in the Codex cloud environment, **Docker and Kubernetes tooling are not available** (including `docker`, `docker-compose`, and `k3d`). This means the instructions in `README.md` that rely on running services via containers or a local k3d cluster will not work here.

Instead, if integration tests or local execution require infrastructure services, the agent should run them **directly as native processes** inside the environment:

- **Postgres**: installed via Ubuntu packages (`postgresql`)
- **NATS**: installed via Ubuntu packages (`nats-server`)
- **Qdrant**: installed as a standalone binary (`qdrant`)

These services are available in the environment, but they are **not started automatically**. Start them manually as needed for tests.

### Postgres Migrations (Reshape)

This project uses **Reshape** to manage Postgres schema migrations.

If you need to write, apply, debug, or review migrations, use:

```sh
reshape docs
```

This prints documentation and guidance for how migrations are structured and managed in this repository.

## Commit Conventions

This repository uses Conventional Commits. All automated agents must follow these rules.

### Commit message format (required)

<type>(<scope>): <subject>

Optional body/footer:

<type>(<scope>): <subject>

<body>

<footer>

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

<scope> is mandatory and must be one of:

- assistant (for the assistant frontend and backend)
- knowledge (for the knowledge interface and GraphRAG)
- infra (for databases, k8s, message broker, IaC etc.)
- tooling (for scripts, dev and test environments, helpers)
- misc

Do not invent new scopes.

### Subject rules

- Use imperative mood (e.g. "add", "fix", "remove")
- No trailing period
- Max 72 characters

Examples:

- feat(assistant): add websocket endpoint for chat
- fix(knowledge): prevent crash on empty query result
- chore(tooling): bump k3s to 1.35.1-k3s1

### Breaking changes

Use either:

feat(assistant)!: remove legacy auth token format

or:

feat(assistant): remove legacy auth token format

BREAKING CHANGE: legacy auth tokens are no longer accepted.

### Atomic commits

Prefer multiple small commits over one large commit, split by intent:

1. refactor (no behavior change)
2. feat/fix (behavior change)
3. tests
4. docs

Each commit should leave the repo in a working state.

### Hygiene

- Do not commit generated build artifacts
- Do not commit secrets
- Keep diffs focused

