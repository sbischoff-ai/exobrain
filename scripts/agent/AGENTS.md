# AGENTS.md (scripts/agent scope)

Applies to `scripts/agent/**`.

## Purpose

Agent-focused scripts for native-process workflows in constrained/cloud environments.

## Canonical scripts

Prefer these for local agent setup and health:

- `native-infra-up.sh`
- `native-infra-health.sh`
- `assistant-db-setup-native.sh`
- `native-infra-down.sh`

App-specific helpers:

- `run-assistant-backend-offline.sh`
- `run-assistant-frontend-mock.sh`
- `run-assistant-frontend-e2e.sh`

## Consistency rules

- Keep script assumptions synchronized with:
  - `docs/agents/codex-runbook.agent.md`
  - `.agent/workflows.yaml`
- If scripts change required services or startup order, update runbook/workflow metadata in the same pass.
- Keep infra coupling aligned with local/dev/deploy manifests when touching service env vars (for example Redis-backed session and DB bootstrap/migration flows).
