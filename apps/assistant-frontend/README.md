# Exobrain Assistant Frontend

SvelteKit application for intro/login gating, journal navigation, and streaming chat UI.

## What this service is

- Cookie-authenticated intro/login flow.
- Journal-focused chat UX with `sessionStorage` snapshots (`exobrain.assistant.session`).
- Workspace view snapshots in `sessionStorage` (`exobrain.assistant.workspaceView`) for mode/explorer continuity.
- SSE-driven streaming message rendering with tool call/response cards.
- Header action to trigger knowledge-base update jobs with live in-progress watch state.
- Mermaid diagram blocks and KaTeX math expressions render in assistant messages.
- Mermaid diagrams render inside a styled, non-transparent panel with side margins for readability.

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
- Chat bubbles show per-message `hh:mm` timestamps sourced from message `created_at` values.
- Logout clears `sessionStorage` snapshot state and returns users to intro gate.
- Workspace mode (`chat`/`knowledge`) and knowledge explorer route/expansion state are restored on bootstrap and persisted on view navigation.
- Knowledge update action appears in the top-right header actions cluster, immediately next to the user menu.
- Knowledge update action is exposed as an accessible circular header control (`aria-label` + tooltip).
- Knowledge update is disabled when viewing a past journal, while app state is loading/syncing, while an update is already in progress, and whenever there are no new messages since the last successful update (`title="nothing to update"`).
- Knowledge browsing service normalizes backend category/page payload fields (`category_id`, `display_name`, `sub_categories`, `knowledge_pages`, `metadata`) into frontend-facing contracts for tree, list, and page detail views.

### Knowledge update flow (high-level)

1. User clicks the header update button for today's journal with new messages available.
2. Frontend enqueues the job via `POST /api/knowledge/update/enqueue`.
3. Frontend opens a watch stream via `GET /api/knowledge/update/{job_id}/watch` (SSE) and tracks status events.
4. Button enters in-progress mode: disabled with `Knowledge update in progress` tooltip and spinner animation.
5. On terminal watch state:
   - `SUCCEEDED`: show success status (`Knowledge base updated successfully.`), stop spinner, and mark current message count as synced.
   - failure/disconnect: show error feedback (`Could not update knowledge base. Please try again.`), stop spinner, and allow retry.

## Related docs

- Docs hub: [`../../docs/README.md`](../../docs/README.md)
- Engineering standards: [`../../docs/standards/engineering-standards.md`](../../docs/standards/engineering-standards.md)
- Agent runbook: [`../../docs/agents/codex-runbook.agent.md`](../../docs/agents/codex-runbook.agent.md)
