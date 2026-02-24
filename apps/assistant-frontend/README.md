# Exobrain Assistant Frontend

SvelteKit application for intro/login gating, journal navigation, and streaming chat UI.

## What this service is

- Cookie-authenticated intro/login flow.
- Journal-focused chat UX with `sessionStorage` snapshots (`exobrain.assistant.session`).
- SSE-driven streaming message rendering with tool call/response cards.

## Quick start

Shared local startup and process orchestration docs:

- [`../../docs/development/local-setup.md`](../../docs/development/local-setup.md)
- [`../../docs/development/process-orchestration.md`](../../docs/development/process-orchestration.md)

Service-only commands:

```bash
./scripts/local/build-assistant-frontend.sh
./scripts/local/run-assistant-frontend.sh
```

Frontend-only mock mode:

```bash
./scripts/agent/run-assistant-frontend-mock.sh
```

## Common commands

```bash
cd apps/assistant-frontend && npm test
./scripts/agent/run-assistant-frontend-e2e.sh
```

## Configuration

- App endpoint: `http://localhost:5173`
- Backend API base (dev proxy target): `http://localhost:8000`
- Logging: keep production runtime logs conservative (`warn` or higher unless explicitly needed).

## Behavior guarantees

- Message APIs are newest-first for pagination; client normalizes to chronological rendering.
- Auto-scroll responds to all message updates, including streaming chunk updates.
- Logout clears `sessionStorage` snapshot state and returns users to intro gate.

## Related docs

- Docs hub: [`../../docs/README.md`](../../docs/README.md)
- Engineering standards: [`../../docs/standards/engineering-standards.md`](../../docs/standards/engineering-standards.md)
- Agent runbook: [`../../docs/agents/codex-runbook.agent.md`](../../docs/agents/codex-runbook.agent.md)
