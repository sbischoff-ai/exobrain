# Exobrain Assistant Frontend

SvelteKit application for intro/login gating, journal navigation, and streaming chat UI.

## What this service is

- Cookie-authenticated intro/login flow.
- Journal-focused chat UX with `sessionStorage` snapshots (`exobrain.assistant.session`).
- Workspace view snapshots in `sessionStorage` (`exobrain.assistant.workspaceView`) for mode/explorer continuity.
- SSE-driven streaming message rendering with tool call/response cards.
- Header action to trigger knowledge-base update jobs with live in-progress watch state.
- Runtime theme switching is driven by user config `frontend.theme` from the user menu, with immediate preview and backend-persisted preference.
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

Run static checks + tests together:

```bash
cd apps/assistant-frontend && ./scripts/verify.sh
```

## Configuration

- App endpoint: `http://localhost:5173`
- Backend API base (dev proxy target): `http://localhost:8000`
- Logging: keep production runtime logs conservative (`warn` or higher unless explicitly needed).

## Behavior guarantees

- Message APIs are newest-first for pagination; client normalizes to chronological rendering.
- Auto-scroll responds to all message updates, including streaming chunk updates.
- Chat composer regains focus automatically when streaming completes and input is re-enabled.
- Chat bubbles show per-message `hh:mm` timestamps sourced from message `created_at` values.
- Logout clears `sessionStorage` snapshot state and returns users to intro gate.
- User menu includes a configs section sourced from `GET /api/users/me/configs`, with choice fields rendered as dropdowns, boolean fields rendered as radio groups, and a `Save changes` action that is enabled only when values differ from backend-loaded state and shows a success notice after persistence.
- Workspace mode (`chat`/`knowledge`) and knowledge explorer route/expansion state are restored on bootstrap and persisted on view navigation.
- Knowledge mode swaps the chat body for a data-backed explorer with `CategoryOverview`, `CategoryPage`, and markdown-rendered `KnowledgePage` detail flows, including breadcrumbs, recursive collapsible category tree navigation, metadata timestamps (`created_at`/`updated_at`), entity-type-specific property rendering from backend-filtered `properties`, related-page cards, and Streamdown rendering parity with chat messages. Page detail now consumes backend `content_blocks` (`block_id` + `markdown`) and renders each block independently in order, preserving prior visual output.
- Knowledge update action appears in the top-right header actions cluster, immediately next to the user menu.
- Theme preview in the user menu updates CSS variables/fonts at runtime without reload; unsaved changes are discarded when the menu is closed.
- Knowledge update action is exposed as an accessible circular header control (`aria-label` + tooltip).
- Knowledge update is disabled when viewing a past journal, while app state is loading/syncing, while an update is already in progress, and whenever there are no new messages since the last successful update (`title="nothing to update"`).
- Knowledge browsing service normalizes backend category/page payload fields (`category_id`, `display_name`, `sub_categories`, `knowledge_pages`, `metadata`) into frontend-facing contracts for tree, category previews, lists, and page detail views.
- Knowledge page metadata timestamps support backend ISO values that include bracketed timezone names (for example, `+00:00[Etc/UTC]`) and render in the explorer's `YYYY/MM/DD HH:mm` format.
- Knowledge explorer cards are fully clickable (card body + title) for category and page navigation.
- Category breadcrumbs always include the full category branch from `Overview` to the active category/page context.
- Category pages render only the selected category subtree in the collapsible tree panel.

### Knowledge Explorer View

- Header mode toggle switches the main workspace between journal chat and knowledge explorer.
- Mode toggle tooltip/accessible label reflects the next target mode:
  - From chat mode: `Switch to Knowledge Explorer`.
  - From knowledge mode: `Switch to Journal Chat`.
- Explorer navigation flow is hierarchical and reversible:
  1. **Overview**: category cards + category tree entrypoint (`explorerRoute.type = "overview"`).
  2. **Category**: selected category detail/listing (`explorerRoute.type = "category"`, `categoryId`).
  3. **Page**: markdown-rendered knowledge page with metadata/related links (`explorerRoute.type = "page"`, `pageId`).
- Route transitions (overview → category → page and back via breadcrumbs/tree clicks) are persisted so refresh/reload restores prior explorer context.
- Category tree expansion state is persisted alongside route state so recursive branch open/closed state survives navigation and reloads.

### Session storage notes (explorer + logout)

- `exobrain.assistant.workspaceView` stores workspace mode (`chat`/`knowledge`), explorer route, and expanded category map for continuity.
- `exobrain.assistant.session` stores active journal reference/message snapshot for chat continuity when switching journals or reloading.
- Logout clears both keys (and pending stream state), then resets UI state to intro-gated chat defaults (chat mode + overview explorer route + no expanded categories).

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
