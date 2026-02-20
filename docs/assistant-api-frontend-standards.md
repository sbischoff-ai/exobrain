# Assistant API + Frontend Architecture Standards

This document captures engineering standards for the assistant backend/frontend integration.

## Frontend layering (assistant-frontend)

Use a TypeScript-first structure with clear responsibilities:

- `src/lib/models/`: shared DTO/domain interfaces for backend payloads and app-level models.
- `src/lib/services/`: backend integration and business orchestration.
  - `apiClient.ts` should stay a thin `fetch` adapter.
  - Domain services (for example `journalService.ts`, `authService.ts`) should contain app-facing workflows.
- `src/lib/stores/`: app state persistence and browser storage contracts.
- `src/lib/utils/`: pure helper utilities.

Keep route/components focused on UI composition and state transitions, not raw endpoint wiring.

## Backend API design (assistant-backend)

- Avoid duplicate endpoints with equivalent behavior.
- Route handlers should delegate into services (`JournalService -> ConversationService -> DatabaseService`).
- Service methods should prefer explicit parameter names (`journal_reference`, `conversation_reference`) and include docstrings.
- Add/maintain type hints in service and API layers.

## Journal/message pagination standard

- Journal entry listing (`GET /api/journal`) uses `reference` as a descending cursor.
- Message listing endpoints use `sequence` as a per-conversation cursor.
- Message queries should default to descending `sequence` so `limit=N` returns newest messages.
- Message create flow sets `sequence` by incrementing the latest sequence number in the same conversation.

## Migration standard (Reshape)

For ordering/pagination schema changes in messages:

- Use an `add_column` migration for `messages.sequence`.
- Include an `up` expression that backfills sequence using `ROW_NUMBER()` partitioned by conversation and ordered by `created_at ASC` (with deterministic tie-breakers).

