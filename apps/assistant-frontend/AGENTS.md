# AGENTS.md (assistant-frontend scope)

Applies to `apps/assistant-frontend/**`.

## Architecture guardrails

- Keep route components thin:
  - API/business flows in `src/lib/services`
  - Persistence mechanics in `src/lib/stores`
  - Shared typed payload contracts in `src/lib/models`

## UI/UX behavior guardrails

- Production logging defaults should remain conservative (`warn` or higher) unless explicitly requested otherwise.
- Intro/journal startup flow depends on cookie-auth intro gating plus `sessionStorage` snapshots (`exobrain.assistant.session`); keep journal sync behavior aligned with `/api/journal/{reference}` and `/api/journal/today` fallback behavior.
- Message APIs are newest-first for pagination; normalize to chronological order before rendering.
- Auto-scroll should react to all message updates, including streaming chunk updates.
- Mermaid pan/zoom controls must stay above diagram content (higher z-index than SVG/`.flowchart`).
- Logout should clear journal snapshots from `sessionStorage` and return the user to intro gating.
- Journal overlay/drawer should be non-layout-shifting, with viewport-anchored left controls and a clearly highlighted "today" entry.

## Agent run scripts

- For frontend-only UI exploration in agent environments, prefer `scripts/agent/run-assistant-frontend-mock.sh`.
- For frontend E2E checks in agent environments, use `scripts/agent/run-assistant-frontend-e2e.sh`.
