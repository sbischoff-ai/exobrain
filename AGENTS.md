# AGENTS.md

This repository uses Conventional Commits. All automated agents must follow these rules.

## Commit message format (required)

<type>(<scope>): <subject>

Optional body/footer:

<type>(<scope>): <subject>

<body>

<footer>

## Allowed types

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

## Allowed scopes (required)

<scope> is mandatory and must be one of:

- assistant (for the assistant frontend and backend)
- knowledge (for the knowledge interface and GraphRAG)
- infra (for databases, k8s, message broker, IaC etc.)
- tooling (for scripts, dev and test environments, helpers)
- misc

Do not invent new scopes.

## Subject rules

- Use imperative mood (e.g. "add", "fix", "remove")
- No trailing period
- Max 72 characters

Examples:

- feat(assistant): add websocket endpoint for chat
- fix(knowledge): prevent crash on empty query result
- chore(tooling): bump k3s to 1.35.1-k3s1

## Breaking changes

Use either:

feat(assistant)!: remove legacy auth token format

or:

feat(assistant): remove legacy auth token format

BREAKING CHANGE: legacy auth tokens are no longer accepted.

## Atomic commits

Prefer multiple small commits over one large commit, split by intent:

1. refactor (no behavior change)
2. feat/fix (behavior change)
3. tests
4. docs

Each commit should leave the repo in a working state.

## Hygiene

- Do not commit generated build artifacts
- Do not commit secrets
- Keep diffs focused

